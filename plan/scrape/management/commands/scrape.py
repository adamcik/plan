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
LOG_LEVELS = {'0': logging.ERROR,
              '1': logging.WARNING,
              '2': logging.INFO,
              '3': logging.DEBUG}

OPTIONS = dict((o.dest, o) for o in management.LabelCommand.option_list + (
        optparse.make_option('-y', '--year', action='store', dest='year', type='int',
                             help='year to scrape'),
        optparse.make_option('-t', '--type', action='store', dest='type',
                             type='choice', choices=dict(Semester.SEMESTER_TYPES).keys(),
                             help='term to scrape'),
        optparse.make_option('-c', '--create', action='store_true', dest='create',
                             help='create missing semester, default: false'),
        optparse.make_option('-n', '--dry-run', action='store_true', dest='dry_run'),
        optparse.make_option('--pdb', action='store_true', dest='pdb',
                             help='use pdb.pm() when we hit and exception'),
))
OPTIONS['verbosity'].default = '2'


class Command(management.LabelCommand):
    option_list = OPTIONS.values()
    help = ('Load data from external sources using specified scraper.\n\n'
            'Available scrapers are:\n  %s' %
            '\n  '.join(sorted(settings.TIMETABLE_SCRAPERS)))

    @transaction.commit_manually
    def handle_label(self, label, **options):
        logging.basicConfig(
            format=CONSOLE_LOG_FORMAT, datefmt=DATE_TIME_FORMAT,
            level=LOG_LEVELS[options['verbosity']])

        try:
            semester = self.load_semester(options)
            scraper = self.load_scraper(label)(semester)

            needs_commit = scraper.run()

            if not needs_commit or options['dry_run']:
                transaction.rollback()
                print 'No changes, rolled back.'
            elif utils.prompt('Commit changes?'):
                transaction.commit()
                print 'Commited changes.'
            else:
                transaction.rollback()
                print 'Rolled back changes.'
        except (SystemExit, KeyboardInterrupt):
            transaction.rollback()
            print 'Rolled back changes due to exit.'
        except:
            try:
                if not options['pdb']:
                    raise

                import pdb, traceback
                traceback.print_exc()
                pdb.post_mortem()
            finally:
                # Ensure that we also rollback after pdb sessions.
                transaction.rollback()
                print 'Rolled back changes due to unhandeled exception.'

    def load_semester(self, options):
        year = options['year']
        type = options['type']

        if not year or not type:
            raise management.CommandError('Semester year and/or type is missing.')

        try:
            return Semester.objects.get(year=year, type=type)
        except Semester.DoesNotExist:
            if not options['create']:
                raise
            return Semester.objects.create(year=year, type=type)

    def load_scraper(self, type):
        try:
            module, cls = settings.TIMETABLE_SCRAPERS.get(type, type).rsplit('.', 1)
            return getattr(importlib.import_module(module), cls)
        except ImportError as e:
            raise management.CommandError('Couldn\'t import %s: %s' % (module, e))
        except AttributeError:
            raise management.CommandError('Scraper %s not found in %s' % (cls, module))
