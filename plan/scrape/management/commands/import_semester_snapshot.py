import json
from pathlib import Path

from django.core.management import BaseCommand, CommandError

from plan.scrape import capture, importing, snapshot


class Command(BaseCommand):
    help = "Reconcile a captured snapshot offline, atomically, without prompting."

    def add_arguments(self, parser):
        parser.add_argument("artifact", type=Path)
        parser.add_argument("--create", action="store_true")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report the diff and roll back every database change.",
        )
        parser.add_argument(
            "--max-delete-percent",
            type=float,
            default=10,
            help="Maximum deletion percentage per entity type. Default 10; use 100 only after reviewing a dry run.",
        )

    def handle(self, *args, **options):
        try:
            artifact = capture.load_snapshot(options["artifact"])
            stats = importing.import_snapshot(
                artifact,
                create=options["create"],
                dry_run=options["dry_run"],
                max_delete_percent=options["max_delete_percent"],
            )
        except (
            snapshot.SnapshotValidationError,
            importing.SnapshotImportError,
        ) as error:
            raise CommandError(str(error)) from error
        self.stdout.write(
            json.dumps(
                {
                    "snapshot_id": str(artifact.manifest.snapshot_id),
                    "dry_run": options["dry_run"],
                    "diff": stats,
                },
                sort_keys=True,
            )
        )
