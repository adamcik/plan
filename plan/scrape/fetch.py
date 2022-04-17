# This file is part of the plan timetable generator, see LICENSE for details.

import collections
import json as jsonlib
import logging
import time
import urllib.parse
import warnings

import lxml.etree
import lxml.html
import requests
from django.core import cache
from django.core.cache import CacheKeyWarning
from django.db import connections
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.exceptions import MaxRetryError
from requests.packages.urllib3.util.retry import Retry

warnings.simplefilter("ignore", CacheKeyWarning)


# Global settings that can be twiddled externally
disable_cache = False
max_per_second = float("inf")


scraper_cache = cache.caches["scraper"]

adapter = HTTPAdapter(
    max_retries=Retry(
        total=3,
        status_forcelist=[429, 502, 503, 504],
        method_whitelist=["GET", "POST"],
        backoff_factor=1,
    )
)

session = requests.Session()
session.mount("https://", adapter)
session.mount("http://", adapter)


class rate_limit:
    previous = 0

    def __init__(self, max_per_second):
        self.interval = 1 / float(max_per_second)

    def __enter__(self):
        delay = self.interval - (time.time() - rate_limit.previous)
        if delay > 0:
            logging.debug("Rate limiter applied for %.3f seconds", delay)
            time.sleep(delay)

    def __exit__(self, type, value, traceback):
        rate_limit.previous = time.time()


def sql(db, query, params=None):
    cursor = connections[db].cursor()
    cursor.execute(query, params or [])
    fields = [col[0] for col in cursor.description]
    row = collections.namedtuple("row", fields)
    for values in cursor.fetchall():
        yield row(*values)


def _fetch(req, key, msg, cache, verbose):
    sentinel = object()
    result = scraper_cache.get(key, default=sentinel)

    if result is sentinel or not cache or disable_cache:
        result = None
        try:
            prepped = session.prepare_request(req)
            with rate_limit(max_per_second):
                response = session.send(prepped, timeout=30)
        except MaxRetryError:
            scraper_cache.set(key, None, timeout=60 * 30)
        else:
            result = response.text
            if response.status_code == 200 and result:
                scraper_cache.set(key, result)
            elif response.status_code == 500:
                scraper_cache.set(key, result, timeout=60 * 30)
    else:
        msg = "Cached hit: %s" % key

    logging.log(logging.INFO if verbose else logging.DEBUG, msg)
    return result


def get(url, cache=True, verbose=False):
    return _fetch(
        requests.Request("GET", url), "get||%s" % (url), "GET: %s" % url, cache, verbose
    )


def post(url, data, cache=True, verbose=False):
    key = f"post||{url}||{urllib.parse.urlencode(data)}"
    msg = f"POST: {url} Data: {data}"
    return _fetch(requests.Request("POST", url, data=data), key, msg, cache, verbose)


def plain(url, query=None, data=None, verbose=False, cache=True):
    if query:
        url += "?" + urllib.parse.urlencode(query)

    try:
        if data is not None:
            return post(url, data, cache=cache, verbose=verbose)
        return get(url, cache=cache, verbose=verbose)
    except OSError as e:
        logging.error("Loading %s failed: %s", url, e)


def html(*args, **kwargs):
    data = plain(*args, **kwargs)
    root = None
    if data:
        root = lxml.html.fromstring(data)
    return root


def json(url, *args, **kwargs):
    data = plain(url, *args, **kwargs)
    if not data:
        logging.error("Loading %s falied: empty repsonse", url)
        return {}
    try:
        return jsonlib.loads(data)
    except ValueError as e:
        logging.error("Loading %s falied: %s", url, e)
        return {}


def xml(*args, **kwargs):
    data = plain(*args, **kwargs)
    if data:
        return lxml.etree.fromstring(data)
    return None
