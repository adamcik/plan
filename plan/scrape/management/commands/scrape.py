# This file is part of the plan timetable generator, see LICENSE for details.

import logging
import optparse

from django.core.management import base as management
from django.conf import settings
from django.db import transaction
from django.utils import importlib

from plan.common.models import Semester

DATE_TIME_FORMAT = '%Y-%m-%d %H:%M:%S'
CONSOLE_LOG_FORMAT = '[%(asctime)s %(levelname)s] %(message)s'

logging.basicConfig(format=CONSOLE_LOG_FORMAT,
                    datefmt=DATE_TIME_FORMAT,
                    level=logging.INFO)

OPTIONS = (
    optparse.make_option('-y', '--year', action='store', dest='year'),
    optparse.make_option('-s', '--spring', action='store_const', dest='type',
                         const=Semester.SPRING),
    optparse.make_option('-f', '--fall', action='store_const', dest='type',
                         const=Semester.FALL),
    optparse.make_option('-m', '--match', action='store', dest='matches',
                         default=None),
)

class Command(management.BaseCommand):
    option_list = management.BaseCommand.option_list + OPTIONS

    def get_semester(self, options):
        semester = Semester.current()

        if options['year'] is not None:
            assert options['year'].isdigit()
            semester.year = options['year']
        if options['type'] is not None:
            semester.type = options['type']

        return semester

    def load_scraper(self, type):
        module, cls = settings.TIMETABLE_SCRAPERS[type].rsplit('.', 1)
        return getattr(importlib.import_module(module), cls)

    def list_items(self, items):
        buffer = []
        for i in items:
            if len(buffer) != 3:
                buffer.append(str(i))
            else:
                print ' | '.join(buffer)
                buffer = []

        if buffer:
            print ' | '.join(buffer)

    @transaction.commit_manually
    def handle(self, *args, **options):
        try:
            assert len(args) == 1, 'usage: ./manage.py scrape <type>'
            assert args[0] in settings.TIMETABLE_SCRAPERS

            semester = self.get_semester(options)

            scraper = self.load_scraper(args[0])(semester, options)
            to_delete = scraper.run()

            if to_delete:
                print 'Delete the following?'
                print '---------------------'
                self.list_items(to_delete)
                print '---------------------'
                print 'Going to delete %d items' % len(to_delete)

                if raw_input('Delete? [y/N] ').lower() == 'y':
                    to_delete.delete()

            if raw_input('Commit changes? [y/N] ').lower() == 'y':
                transaction.commit()
                print 'Commiting changes...'
            else:
                transaction.rollback()
                print 'Rolling back changes...'
        except:
            transaction.rollback()
            raise
