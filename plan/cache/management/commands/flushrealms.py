# Copyright 2010 Thomas Kongevold Adamcik

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
from optparse import make_option

from django.core.management.base import BaseCommand

from plan.cache import clear_cache
from plan.common.logger import init_console
from plan.common.models import Semester, Student

init_console()

logger = logging.getLogger()

class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
            make_option('-y', '--year', action='store', dest='year'),
            make_option('-s', '--spring', action='store_const', dest='type', const=Semester.SPRING),
            make_option('-f', '--fall', action='store_const', dest='type', const=Semester.FALL),
        )

    def handle(self, *args, **options):
        semester = Semester.current()

        if options['year'] is not None:
            semester.year = options['year']

        if options['type'] is not None:
            semester.type = options['type']

        logger.info('Flushing cache for %s', semester)

        students = Student.objects.filter(
            subscription__course__semester__year__exact=semester.year,
            subscription__course__semester__type=semester.type)

        for student in students.distinct().order_by('slug'):
            clear_cache(semester, student.slug)
