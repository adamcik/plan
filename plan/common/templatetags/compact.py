# This file is part of the plan timetable generator, see LICENSE for details.

from django import template

from plan.common.utils import compact_sequence

register = template.Library()

register.filter('compact', compact_sequence)
