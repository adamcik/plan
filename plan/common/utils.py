# Copyright 2008, 2009 Thomas Kongevold Adamcik
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

import datetime
import operator
from dateutil import rrule

from django import http
from django import template
from django.conf import settings
from django.db import models
from django.utils import text as text_utils


def build_search(searchstring, filters, max_query_length=4,
                 combine=operator.and_):
    count = 0
    search_filter = models.Q()

    for word in text_utils.smart_split(searchstring):
        if word[0] in ['"', "'"]:
            if word[0] == word[-1]:
                word = word[1:-1]
            else:
                word = word[1:]

        if count > max_query_length:
            break

        local_filter = models.Q()
        for f in filters:
            local_filter |= models.Q(**{f: word})

        search_filter = combine(search_filter, local_filter)
        count += 1

    return search_filter


def server_error(request, template_name='500.html'):
    """
    500 error handler.

    Templates: `500.html`
    Context: None
    """
    # You need to create a 500.html template.
    t = template.loader.get_template(template_name)

    context = template.Context({'MEDIA_URL': settings.MEDIA_URL,
                                'STATIC_URL': settings.STATIC_URL,
                                'SOURCE_URL': settings.SOURCE_URL})

    return http.HttpResponseServerError(t.render(context))


def compact_sequence(sequence):
    '''Compact sequences of numbers into array of strings [i, j, k-l, n-m]'''
    if not sequence:
        return []

    sequence.sort()

    compact = []
    first = sequence[0]
    last = sequence[0] - 1

    for item in sequence:
        if last == item - 1:
            last = item
        else:
            if first != last:
                compact.append('%d-%d' % (first, last))
            else:
                compact.append('%d' % first)

            first = item
            last = item

    if first != last:
        compact.append('%d-%d' % (first, last))
    else:
        compact.append('%d' % first)

    return compact


class ColorMap(dict):
    """Magic dict that assigns colors"""

    # Colors from www.ColorBrewer.org by Cynthia A. Brewer, Geography,
    # Pennsylvania State University.
    # http://www.personal.psu.edu/cab38/ColorBrewer/ColorBrewer_updates.html

    def __init__(self, index=0, hex=False):
        self.index = index
        self.max = len(settings.TIMETABLE_COLORS)
        self.hex = hex

    def __getitem__(self, k):
        # Remember to use super to prevent inf loop
        if k is None:
            return ''

        if k in self:
            return super(ColorMap, self).__getitem__(k)
        else:
            self.index += 1
            if self.hex:
                self[k] = settings.TIMETABLE_COLORS[self.index % self.max]
            else:
                self[k] = 'color%d' % (self.index % self.max)
            return super(ColorMap, self).__getitem__(k)


def max_number_of_weeks(year):
    if list(rrule.rrule(rrule.WEEKLY, count=1, byweekno=53, byweekday=rrule.MO,
            dtstart=datetime.date(year, 1, 1)))[0].year == year:
        return 53
    return 52

