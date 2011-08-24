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

import logging
from optparse import make_option

from django.core.management.base import BaseCommand
from django.db import transaction

from plan.scrape.db import update_lectures as update_lectures_from_db
from plan.scrape.web import update_lectures as update_lectures_from_web
from plan.common.models import Semester, Lecture
from plan.common.logger import init_console

init_console()

logger = logging.getLogger()

class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
            make_option('-w', '--web', action='store_true', dest='web',
                default=False, help="Use web as source"),
            make_option('-y', '--year', action='store', dest='year'),
            make_option('-s', '--spring', action='store_const', dest='type', const=Semester.SPRING),
            make_option('-f', '--fall', action='store_const', dest='type', const=Semester.FALL),
            make_option('-d', '--delete', action='store_const', dest='delete', const=1),
            make_option('-m', '--matches', action='store', dest='matches', default=None),
        )

    @transaction.commit_manually
    def handle(self, *args, **options):
        try:
            semester = Semester.current()

            if options['year'] is not None:
                semester.year = options['year']

            if options['type'] is not None:
                semester.type = options['type']

            logger.info('Updating lectures for %s', semester)

            if options['web']:
                to_delete = update_lectures_from_web(semester.year, semester.type, matches=options['matches'])
            else:
                to_delete = update_lectures_from_db(semester.year, semester.type, matches=options['matches'])

            if to_delete:
                print 'Delete the following?'
                print '---------------------'

                buffer = []
                for l in to_delete:
                    if len(buffer) != 3:
                        buffer.append(str(l))
                    else:
                        print ' | '.join(buffer)
                        buffer = []

                if buffer:
                    print ' | '.join(buffer)

                lecutre_count = Lecture.objects.filter(
                    course__semester__year__exact=semester.year,
                    course__semester__type=semester.type).count()

                print '---------------------'
                print 'Lectures left %d' % (lecutre_count - len(to_delete))
                print 'Going to delete %d lectures' % len(to_delete)

                if options['delete'] or raw_input('Delete? [y/N] ').lower() == 'y':
                    to_delete.delete()

            if raw_input('Save changes? [y/N] ').lower() == 'y':
                transaction.commit()
                print 'Saving changes...'
            else:
                transaction.rollback()
                print 'Ignoring changes...'

        except:
            transaction.rollback()
            raise
