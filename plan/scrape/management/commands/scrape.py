# This file is part of the plan timetable generator, see LICENSE for details.

import logging
import optparse
import sys

from django.core.management import base as management
from django.conf import settings
from django.db import transaction
from django.utils import importlib

from plan.common.models import Semester
from plan.scrape import utils

DATE_TIME_FORMAT = '%Y-%m-%d %H:%M:%S'
CONSOLE_LOG_FORMAT = '[%(asctime)s %(levelname)s] %(message)s'

logging.basicConfig(format=CONSOLE_LOG_FORMAT,
                    datefmt=DATE_TIME_FORMAT,
                    level=logging.INFO)

make_option = optparse.make_option


class Command(management.LabelCommand):
    help = 'Load data from external sources using specified scraper.'

    option_list = management.BaseCommand.option_list + (
        make_option('-y', '--year', action='store', dest='year',
                    help='yearp to scrape'),
        make_option('-t', '--type', action='store', dest='type',
                    help='term to scrape'),
        make_option('-c', '--create', action='store_const',
                    dest='create', const=True, default=False,
                    help='create missing semester, default: false'),
    )

    @transaction.commit_manually
    def handle_label(self, label, **options):
        try:
            semester = self.load_semester(options)
            scraper = self.load_scraper(label)(semester)

            to_delete = scraper.run()

            if to_delete:
                print 'Delete the following?'
                print utils.columnify(to_delete)
                print 'Going to delete %d items' % to_delete.count()

                if utils.prompt('Delete?'):
                    to_delete.delete()

            if not scraper.needs_commit:
                transaction.rollback()
            elif utils.prompt('Commit changes?'):
                transaction.commit()
                print 'Commited changes.'
            else:
                transaction.rollback()
                print 'Rolled back changes.'
        except:
            transaction.rollback()
            raise

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
        try:
            module, cls = settings.TIMETABLE_SCRAPERS.get(type, type).rsplit('.', 1)
            return getattr(importlib.import_module(module), cls)
        except ImportError as e:
            raise management.CommandError('Couldn\'t import %s: %s' % (module, e))
        except AttributeError:
            raise management.CommandError('Scraper %s not found in %s' % (cls, module))
