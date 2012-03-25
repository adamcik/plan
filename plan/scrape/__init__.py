# Copyright 2011 Thomas Kongevold Adamcik

# This file is part of Plan.
#
# Plan is free software: you can redistribute it and/or modify
# it under the terms of the Affero GNU General Public License as
# published by the Free Software Foundation, either version 3 of
# the License, or (at your option) any later version.
#
# Plan is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# Affero GNU General Public License for more details.
#
# You should have received a copy of the Affero GNU General Public
# License along with Plan.  If not, see <http://www.gnu.org/licenses/>.

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
