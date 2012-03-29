# This file is part of the plan timetable generator, see LICENSE for details.

import urllib

from django.conf import settings
from django.core import cache

def fetch_url(url):
    """Act as "proxy" for scraped pages, using cache when possible."""
    scrape_cache = cache.get_cache('webscraper')

    data = scrape_cache.get(url)
    if not data:
        data = urllib.urlopen(url).read()
        scrape_cache.set(url, data)
    return data
