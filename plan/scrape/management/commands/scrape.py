# This file is part of the plan timetable generator, see LICENSE for details.

import logging
import optparse
import sys

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

make_option = optparse.make_option


class Command(management.BaseCommand):
    option_list = management.BaseCommand.option_list + (
        make_option('-y', '--year', action='store', dest='year',
                    help='yearp to scrape'),
        make_option('-t', '--type', action='store', dest='type',
                    help='term to scrape'),
        make_option('-c', '--create', action='store_const',
                    dest='create', const=True, default=False,
                    help='create missing semester, default: false'),
    )

    def load_semester(self, options):
        semester = Semester.current()
        semester.year = options.get('year', None) or semester.year
        semester.type = options.get('type', None) or semester.type

        if semester.type not in dict(Semester.SEMESTER_TYPES):
            raise management.CommandError('Invalid semester type: %s' % semester.type)
        elif not str(semester.year).isdigit():
            raise management.CommandError('Invalid semester year: %s' % semester.year)

        try:
            return Semester.objects.get(
                year=semester.year, type=semester.type)
        except Semester.DoesNotExist:
            if not options['create']:
                raise
            return semester.save()

    def load_scraper(self, type):
        module, cls = settings.TIMETABLE_SCRAPERS[type].rsplit('.', 1)
        return getattr(importlib.import_module(module), cls)

    def list_items(self, items, n=3):
        items = map(unicode, items)
        size = max(map(len, items))
        border = unicode('+-' + '-+-'.join(['-'*size]*n) + '-+')
        template = unicode('| ' + ' | '.join(['{:%d}' % size]*n) + ' |')
        pad = lambda i: i + ['']*(n-len(i))

        print border
        while items:
            print template.format(*pad(items[:n]))
            items = items[n:]
        print border

    def prompt(self, message):
        try:
            return raw_input('%s [y/N] ' % message).lower() == 'y'
        except KeyboardInterrupt:
            sys.exit(1)

    @transaction.commit_manually
    def handle(self, *args, **options):
        # TODO(adamcik): move as much as we can to scraper.
        # - list items in scraper
        # - delete prompting etc
        # - prompt should be in utils

        try:
            if len(args) != 1:
                raise management.CommandError('Please specify scraper to use.')
            elif args[0] not in settings.TIMETABLE_SCRAPERS:
                raise management.CommandError('Unknown scraper: %s' % args[0])

            semester = self.load_semester(options)
            scraper = self.load_scraper(args[0])(semester)

            to_delete = scraper.run()

            if to_delete:
                print 'Delete the following?'
                # TODO(adamcik): use scraper.display()
                self.list_items(to_delete)
                print 'Going to delete %d items' % to_delete.count()

                if self.prompt('Delete?'):
                    to_delete.delete()

            if not scraper.needs_commit:
                transaction.rollback()
            elif self.prompt('Commit changes?'):
                transaction.commit()
                print 'Commiting changes...'
            else:
                transaction.rollback()
                print 'Rolling back changes...'
        except:
            transaction.rollback()
            raise
