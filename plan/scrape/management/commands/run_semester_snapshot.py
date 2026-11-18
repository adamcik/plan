import datetime
import uuid
from pathlib import Path

from django.core.management import BaseCommand, CommandError, call_command

from plan.scrape import _archive, capture


class Command(BaseCommand):
    help = "Start a fresh source capture run; safe for a recurring cron job or timer."

    def add_arguments(self, parser):
        parser.add_argument("--year", type=int, required=True)
        parser.add_argument("--type", choices=("spring", "fall"), required=True)
        parser.add_argument(
            "--directory",
            type=Path,
            required=True,
            help="Private archive root. Every invocation starts a new run directory; retention is operator-managed.",
        )
        parser.add_argument(
            "--capture",
            default="ntnu",
            help="Capture registered in TIMETABLE_CAPTURES.",
        )
        parser.add_argument("--job", action="append", dest="jobs")
        parser.add_argument("--max-per-second", type=float, default=5)

    def handle(self, *args, **options):
        try:
            with _archive.locked_directory(
                options["directory"], lock_name=".capture.lock"
            ) as directory:
                self._capture(directory, options)
        except _archive.ArchiveError as error:
            raise CommandError(
                "another snapshot run is using this archive root"
            ) from error

    def _capture(self, directory, options):
        timestamp = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%S.%fZ")
        run = (
            directory
            / f"{options['year']}-{options['type']}-{timestamp}-{uuid.uuid4().hex}"
        )

        call_command(
            "capture_semester_snapshot",
            options["capture"],
            year=options["year"],
            type=options["type"],
            directory=run,
            jobs=options["jobs"],
            max_per_second=options["max_per_second"],
            stdout=self.stdout,
            stderr=self.stderr,
        )
        self.stdout.write(f"Archived snapshot: {run / capture.MANIFEST_NAME}")
