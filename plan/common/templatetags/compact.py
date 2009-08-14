# Copyright 2009 Thomas Kongevold Adamcik
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

from django import template

from plan.common.utils import compact_sequence

register = template.Library()

@register.filter
def compact(sequence):
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
