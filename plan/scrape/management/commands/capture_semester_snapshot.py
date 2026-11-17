import datetime
import math
from pathlib import Path

from django.conf import settings
from django.core.management import BaseCommand, CommandError
from django.utils.module_loading import import_string

from plan.scrape import capture, snapshot


class Command(BaseCommand):
    help = "Archive opaque source responses without importing or normalizing them."

    def add_arguments(self, parser):
        parser.add_argument("capture", nargs="?", default="ntnu")
        parser.add_argument("--year", required=True, type=int)
        parser.add_argument("--type", required=True, choices=("spring", "fall"))
        parser.add_argument(
            "--directory",
            required=True,
            type=Path,
            help="Directory for this run's manifest and response JSON files.",
        )
        parser.add_argument(
            "--resume",
            action="store_true",
            help="Reuse this run's successes and retry missing or failed requests. Completed runs are unchanged.",
        )
        parser.add_argument(
            "--job",
            action="append",
            dest="jobs",
            help="Source-specific acquisition job; repeat to select jobs. Discovery dependencies remain source-owned.",
        )
        parser.add_argument("--max-per-second", type=float, default=5)
        parser.add_argument(
            "--max-resume-age-hours",
            type=float,
            default=24,
            help="Maximum total capture age when resuming. Start a new directory for fresh weekly observations.",
        )

    def handle(self, *args, **options):
        for name in ("max_per_second", "max_resume_age_hours"):
            if not math.isfinite(options[name]) or options[name] <= 0:
                raise CommandError(
                    f"{name.replace('_', '-')} must be finite and positive"
                )

        try:
            semester = snapshot.Semester(year=options["year"], type=options["type"])
            registry = getattr(settings, "TIMETABLE_CAPTURES", {})
            if options["capture"] not in registry:
                raise capture.CaptureError(f"unknown capture: {options['capture']}")

            adapter = import_string(registry[options["capture"]])(
                semester,
                jobs=options["jobs"],
                max_per_second=options["max_per_second"],
            )

            manifest = capture.run_capture(
                adapter,
                semester,
                options["directory"],
                resume=options["resume"],
                max_resume_age=datetime.timedelta(
                    hours=options["max_resume_age_hours"]
                ),
            )
        except (ValueError, OSError, ImportError, AttributeError) as error:
            raise CommandError(str(error)) from error

        self.stdout.write(
            f"Capture {manifest.snapshot_id}: {manifest.status}; {options['directory'] / capture.MANIFEST_NAME}"
        )

        if manifest.status != snapshot.RunStatus.COMPLETE:
            raise CommandError("capture incomplete; archived results can be resumed")
