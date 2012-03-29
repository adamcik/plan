# Copyright 2009, 2010 Thomas Kongevold Adamcik
# 2009 IME Faculty Norwegian University of Science and Technology

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

import logging

from django.core.cache.backends.dummy import CacheClass as DummyCacheClass

from plan import cache
from plan.common.models import Semester


class CacheMiddleware(object):
    '''Attaches either a real or dummy cache instance to our request, cache
       instance should only be used for retrival'''

    def __init__(self):
        self.logger = logging.getLogger('plan.middleware.cache')

    def process_view(self, request, view_func, view_args, view_kwargs):
        if 'year' in view_kwargs and 'semester_type' in view_kwargs:
            semester = Semester(year=view_kwargs['year'],
                type=view_kwargs['semester_type'])
        else:
            semester = Semester.current()

        slug = view_kwargs.get('slug', None)
        realm = cache.get_realm(semester, slug)
        bypass = self._ignore_cache(request)
        request.cache = cache.CacheClass(realm=realm, bypass=bypass)

    def _ignore_cache(self, request):
        return (request.META.get('HTTP_CACHE_CONTROL', '').lower() == 'no-cache' or
                'no-cache' in request.GET)
