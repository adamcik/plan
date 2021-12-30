# This file is part of the plan timetable generator, see LICENSE for details.

import collections
import json as jsonlib
import logging
import lxml.etree
import lxml.html
import time
import warnings
import urllib

import requests

from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

from django.core import cache
from django.db import connections
from django.core.cache import CacheKeyWarning

warnings.simplefilter('ignore', CacheKeyWarning)


# Global settings that can be twiddled externally
disable_cache = False
max_per_second = float('inf')


scraper_cache = cache.caches['scraper']

adapter = HTTPAdapter(max_retries=Retry(
    total=3,
    status_forcelist=[429, 500, 502, 503, 504],
    method_whitelist=['GET', 'POST'],
    backoff_factor=1,
))

session = requests.Session()
session.mount("https://", adapter)
session.mount("http://", adapter)


class rate_limit(object):
    previous = 0

    def __init__(self, max_per_second):
        self.interval = 1 / float(max_per_second)

    def __enter__(self):
        delay = self.interval - (time.time() - rate_limit.previous)
        if delay > 0:
            logging.debug('Rate limiter applied for %.3f seconds', delay)
            time.sleep(delay)

    def __exit__(self, type, value, traceback):
         rate_limit.previous = time.time()


def sql(db, query, params=None):
    cursor = connections[db].cursor()
    cursor.execute(query, params or [])
    fields = [col[0] for col in cursor.description]
    row = collections.namedtuple('row', fields)
    for values in cursor.fetchall():
        yield row(*values)


def get(url, cache=True, verbose=False):
    key = 'get||%s' % (url)
    result = scraper_cache.get(key)
    msg = 'Cached fetch: %s' % url
    if not result or not cache or disable_cache:
        msg = 'Fetched: %s' % url
        with rate_limit(max_per_second):
            response = session.get(url, timeout=30)
        result = response.text
        if response.status_code == 200 and result:
            scraper_cache.set(key, result)

    logging.log(logging.INFO if verbose else logging.DEBUG, msg)
    return result


def post(url, data, cache=True, verbose=False):
    key = 'post||%s||%s' % (url, urllib.urlencode(data))
    result = scraper_cache.get(key)
    msg = 'Cached result found under: %s' % key

    if not result or not cache or disable_cache:
        msg = 'Post: %s Data: %s' % (url, data)
        with rate_limit(max_per_second):
            response = session.post(url, data=data, timeout=30)
        result = response.text
        if response.status_code == 200 and result:
            scraper_cache.set(key, result)

    logging.log(logging.INFO if verbose else logging.DEBUG, msg)
    return result


def plain(url, query=None, data=None, verbose=False, cache=True):
    if query:
        url += '?' + urllib.urlencode(query)

    try:
        if data is not None:
            return post(url, data, cache=cache, verbose=verbose)
        return get(url, cache=cache, verbose=verbose)
    except IOError as e:
        logging.error('Loading %s failed: %s', url, e)


def html(*args, **kwargs):
    data = plain(*args, **kwargs)
    root = None
    if data:
        root = lxml.html.fromstring(data)
    return root


def json(url, *args, **kwargs):
    data = plain(url, *args, **kwargs)
    if not data:
        logging.error('Loading %s falied: empty repsonse', url)
        return {}
    try:
        return jsonlib.loads(data)
    except ValueError as e:
        logging.error('Loading %s falied: %s', url, e)
        return {}


def xml(*args, **kwargs):
    data = plain(*args, **kwargs)
    if data:
        return lxml.etree.fromstring(data)
    return None
