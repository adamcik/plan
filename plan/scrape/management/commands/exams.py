# This file is part of the plan timetable generator, see LICENSE for details.

import logging
from optparse import make_option

from django.core.management.base import BaseCommand
from django.db import transaction

from plan.scrape.studweb import update_exams
from plan.common.models import Exam, Semester
from plan.common.logger import init_console

init_console()

logger = logging.getLogger()

class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
            make_option('-y', '--year', action='store', dest='year'),
            make_option('-s', '--spring', action='store_const', dest='type', const=Semester.SPRING),
            make_option('-f', '--fall', action='store_const', dest='type', const=Semester.FALL),
            make_option('-d', '--delete', action='store_const', dest='delete', const=1),
        )

    @transaction.commit_manually
    def handle(self, *args, **options):
        try:
            semester = Semester.current()

            if options['year'] is not None:
                semester.year = options['year']

            if options['type'] is not None:
                semester.type = options['type']

            logger.info('Updating exams for %s', semester)

            to_delete = update_exams(semester.year, semester.type)

            if to_delete:
                print 'Delete the following?'
                print '---------------------'

                buffer = []
                for l in to_delete:
                    if len(buffer) != 3:
                        buffer.append(str(l).ljust(15)[:14])
                    else:
                        print ' - '.join(buffer)
                        buffer = []

                if buffer:
                    print ' - '.join(buffer)

                print '---------------------'

                if options['delete'] or raw_input('Delete? [y/N] ').lower() == 'y':
                    Exam.objects.filter(id__in=[e.id for e in to_delete]).delete()

            if raw_input('Save changes? [y/N] ').lower() == 'y':
                transaction.commit()
                print 'Saving changes...'
            else:
                transaction.rollback()
                print 'Ignoring changes...'

        except:
            transaction.rollback()
            raise
