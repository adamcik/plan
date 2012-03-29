# This file is part of the plan timetable generator, see LICENSE for details.

import logging
from optparse import make_option

from django.core.management.base import BaseCommand
from django.db import transaction

from plan.scrape.sit import update_syllabus
from plan.common.models import Semester
from plan.common.logger import init_console

init_console()

logger = logging.getLogger()

class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
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

            logger.info('Updating syllabus for %s', semester)

            update_syllabus(semester.year, semester.type, options['matches'])

            if raw_input('Save changes? [y/N] ').lower() == 'y':
                transaction.commit()
                print 'Saving changes...'
            else:
                transaction.rollback()
                print 'Ignoring changes...'

        except:
            transaction.rollback()
            raise
