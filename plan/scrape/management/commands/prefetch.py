# This file is part of the plan timetable generator, see LICENSE for details.

import importlib
import logging

from django.conf import settings
from django.core.management import base as management

from plan.common.models import Semester
from plan.scrape import fetch

DATE_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"
CONSOLE_LOG_FORMAT = "[%(asctime)s %(levelname)s] %(message)s"
LOG_LEVELS = {0: logging.ERROR, 1: logging.WARNING, 2: logging.INFO, 3: logging.DEBUG}


class Command(management.BaseCommand):
    help = "Prefetch data from external sources"

    def add_arguments(self, parser):
        super().add_arguments(parser)

        # TODO: Get rid of need for this in load_semester?
        parser.add_argument(
            "-c",
            "--create",
            action="store_true",
            dest="create",
            help="create missing semester, default: false",
        ),

        parser.add_argument(
            "-y", "--year", action="store", dest="year", type=int, help="year to scrape"
        )
        parser.add_argument(
            "-t",
            "--type",
            action="store",
            dest="type",
            choices=list(dict(Semester.SEMESTER_TYPES).keys()),
            help="term to scrape",
        )
        parser.add_argument(
            "--pdb",
            action="store_true",
            dest="pdb",
            help="use pdb.pm() when we hit and exception",
        )
        parser.add_argument(
            "--prefix",
            action="store",
            dest="prefix",
            help="course code prefix to limit scrape to",
        )
        parser.add_argument(
            "--disable_cache", action="store_true", dest="disable_cache"
        )
        parser.add_argument(
            "--max_per_second",
            action="store",
            default=5,
            dest="max_per_second",
            type=float,
        )

    def handle(self, **options):
        logging.basicConfig(
            format=CONSOLE_LOG_FORMAT,
            datefmt=DATE_TIME_FORMAT,
            level=LOG_LEVELS[options["verbosity"]],
        )

        fetch.disable_cache = options["disable_cache"]
        fetch.max_per_second = options["max_per_second"] or float("inf")

        try:
            semester = self.load_semester(options)
            for scraper in self.load_scrapers():
                scraper(semester, options["prefix"]).prefetch()
        except:
            if not options["pdb"]:
                raise

            import pdb
            import traceback

            traceback.print_exc()
            pdb.post_mortem()

    def load_semester(self, options):
        year = options["year"]
        type = options["type"]

        if not year or not type:
            raise management.CommandError("Semester year and/or type is missing.")

        try:
            return Semester.objects.get(year=year, type=type)
        except Semester.DoesNotExist:
            if not options["create"]:
                raise
            return Semester.objects.create(year=year, type=type)

    def load_scrapers(self):
        # TODO: Some of the scrapers depend on courses being loaded, handle this somehow?
        scrapers = []
        for scraper in settings.TIMETABLE_SCRAPERS_PREFETCH:
            try:
                module, cls = scraper.rsplit(".", 1)
                scrapers.append(getattr(importlib.import_module(module), cls))
            except ImportError as e:
                raise management.CommandError(f"Couldn't import {module}: {e}")
            except AttributeError:
                raise management.CommandError(f"Scraper {cls} not found in {module}")
        return scrapers
