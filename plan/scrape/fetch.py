# This file is part of the plan timetable generator, see LICENSE for details.

import json as jsonlib
import logging
import lxml.etree
import lxml.html
import urllib

from django.core import cache

scraper_cache = cache.get_cache('scraper')


def get(url, cache=True, verbose=False):
    data = scraper_cache.get(url)
    msg = 'Cached fetch: %s' % url
    if not data or not cache:
        msg = 'Fetched: %s' % url
        response = urllib.urlopen(url)
        data = response.read()
        if response.getcode() == 200 and data:
            scraper_cache.set(url, data)

    logging.log(logging.INFO if verbose else logging.DEBUG, msg)
    return data


def plain(url, query=None, verbose=False, cache=True):
    if query:
        url += '?' + urllib.urlencode(query)

    try:
       return get(url, cache=cache, verbose=verbose)
    except IOError as e:
        logging.error('Loading %s falied: %s', url, e)


def html(*args, **kwargs):
    data = plain(*args, **kwargs)
    root = None
    if data:
        root = lxml.html.fromstring(data)
    if root is not None:
        root.make_links_absolute(args[0])
    return root


def json(*args, **kwargs):
    data = plain(*args, **kwargs)
    if data:
        return jsonlib.loads(data)
    return {}


def xml(*args, **kwargs):
    data = plain(*args, **kwargs)
    if data:
        return lxml.etree.fromstring(data)
    return None
