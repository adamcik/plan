# This file is part of the plan timetable generator, see LICENSE for details.

import json as jsonlib
import logging
import lxml.etree
import lxml.html
import urllib

from django.core import cache

scraper_cache = cache.get_cache('scraper')


def get(url, cache=True):
    data = scraper_cache.get(url)
    if not data or not cache:
        response = urllib.urlopen(url)
        data = response.read()
        if response.getcode() == 200 and data:
            scraper_cache.set(url, data)
    return data


def plain(url, query=None, verbose=False, cache=True):
    if query:
        url += '?' + urllib.urlencode(query)

    if verbose:
        logging.info('Retrieving: %s' % url)
    else:
        logging.debug('Retrieving: %s' % url)

    try:
       return get(url, cache=cache)
    except IOError as e:
        logging.error('Loading %s falied: %s', url, e)


def html(*args, **kwargs):
    data = plain(*args, **kwargs)
    if data:
        return lxml.html.fromstring(data)
    return None


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
