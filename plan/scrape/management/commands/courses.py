import logging
from optparse import make_option

from django.core.management.base import BaseCommand
from django.db import transaction

from plan.scrape.db import update_courses
from plan.common.models import Semester
from plan.common.logger import init_console

init_console()

logger = logging.getLogger()

class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
            make_option('-y', '--year', action='store', dest='year'),
            make_option('-s', '--spring', action='store_const', dest='type', const=Semester.SPRING),
            make_option('-f', '--fall', action='store_const', dest='type', const=Semester.FALL),
        )

    @transaction.commit_manually
    def handle(self, *args, **options):
        semester = Semester.current()

        if options['year'] is not None:
            semester.year = options['year']

        if options['type'] is not None:
            semester.type = options['type']

        logger.info('Updating exams for %s', semester)

        update_courses(semester.year, semester.type)

        if raw_input('Save changes? [y/N] ').lower() == 'y':
            transaction.commit()
            print 'Saving changes...'
        else:
            transaction.rollback()
            print 'Ignoring changes...'
