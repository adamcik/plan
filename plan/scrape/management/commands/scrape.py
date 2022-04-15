# This file is part of the plan timetable generator, see LICENSE for details.

from __future__ import absolute_import
from __future__ import print_function
import importlib
import logging
import sys

from django.core.management import base as management
from django.conf import settings
from django.db import transaction

from plan.common.models import Semester
from plan.scrape import fetch, utils

DATE_TIME_FORMAT = '%Y-%m-%d %H:%M:%S'
CONSOLE_LOG_FORMAT = '[%(asctime)s %(levelname)s] %(message)s'
LOG_LEVELS = {0: logging.ERROR,
              1: logging.WARNING,
              2: logging.INFO,
              3: logging.DEBUG}


class Command(management.LabelCommand):
    help = ('Load data from external sources using specified scraper.\n\n'
            'Available scrapers are:\n  %s' %
            '\n  '.join(sorted(settings.TIMETABLE_SCRAPERS)))

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)

        parser.add_argument('-y', '--year', action='store', dest='year', type=int,
                             help='year to scrape')
        parser.add_argument('-t', '--type', action='store', dest='type',
                             choices=list(dict(Semester.SEMESTER_TYPES).keys()),
                             help='term to scrape')
        parser.add_argument('-c', '--create', action='store_true', dest='create',
                             help='create missing semester, default: false'),
        parser.add_argument('-n', '--dry-run', action='store_true', dest='dry_run')
        parser.add_argument('--pdb', action='store_true', dest='pdb',
                             help='use pdb.pm() when we hit and exception')
        parser.add_argument('--prefix', action='store', dest='prefix',
                             help='course code prefix to limit scrape to')
        parser.add_argument('--disable_cache', action='store_true',
                            dest='disable_cache')
        parser.add_argument('--max_per_second', action='store', default=5,
                            dest='max_per_second', type=float)

    @transaction.atomic
    def handle_label(self, label, **options):
        logging.basicConfig(
            format=CONSOLE_LOG_FORMAT, datefmt=DATE_TIME_FORMAT,
            level=LOG_LEVELS[options['verbosity']])

        fetch.disable_cache = options['disable_cache']
        fetch.max_per_second = options['max_per_second'] or float('inf')

        sid = transaction.savepoint()

        try:
            semester = self.load_semester(options)
            scraper = self.load_scraper(label)(semester, options['prefix'])

            needs_commit = scraper.run()

            if not needs_commit or options['dry_run']:
                transaction.savepoint_rollback(sid)
                print('No changes, rolled back.')
            elif utils.prompt('Commit changes?'):
                transaction.savepoint_commit(sid)
                print('Commiting changes.')
            else:
                transaction.savepoint_rollback(sid)
                print('Rolled back changes.')
        except (SystemExit, KeyboardInterrupt):
            transaction.savepoint_rollback(sid)
            print('Rolled back changes due to exit.')
        except:
            try:
                if not options['pdb']:
                    raise

                import pdb, traceback
                traceback.print_exc()
                pdb.post_mortem()
            finally:
                # Ensure that we also rollback after pdb sessions.
                transaction.savepoint_rollback(sid)
                print('Rolled back changes due to unhandeled exception.')

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
