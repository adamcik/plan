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

import os
import urllib

from django.conf import settings
from django.core.cache import get_cache

cache = get_cache(
    'file://%s' % os.path.join(settings.BASE_PATH, 'cache'))

def fetch_url(url):
    data = cache.get(url)

    if data:
        return data

    data = urllib.urlopen(url).read()
    cache.set(url, data, 3600*31)
    return data
