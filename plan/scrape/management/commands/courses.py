# This file is part of the plan timetable generator, see LICENSE for details.

import logging
from optparse import make_option

from django.core.management.base import BaseCommand
from django.db import transaction

from plan.scrape.db import update_courses as update_courses_from_db
from plan.scrape.web import update_courses as update_courses_from_web
from plan.common.models import Semester, Course
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
        )

    @transaction.commit_manually
    def handle(self, *args, **options):
        try:
            semester = Semester.current()

            if options['year'] is not None:
                semester.year = options['year']

            if options['type'] is not None:
                semester.type = options['type']

            logger.info('Updating courses for %s', semester)

            # FIXME get courses for semester and delete those not added?

            if options['web']:
                update_courses_from_web(semester.year, semester.type)
            else:
                update_courses_from_db(semester.year, semester.type)

            for course in Course.objects.filter(semester__year__exact=semester.year,
                    semester__type=semester.type):
                course.url = 'http://www.ntnu.no/studier/emner/%s' % course.code
                course.save()

            if raw_input('Save changes? [y/N] ').lower() == 'y':
                transaction.commit()
                print 'Saving changes...'
            else:
                transaction.rollback()
                print 'Ignoring changes...'

        except:
            transaction.rollback()
            raise
