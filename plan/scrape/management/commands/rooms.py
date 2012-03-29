# This file is part of the plan timetable generator, see LICENSE for details.

import logging

from django.core.management.base import BaseCommand
from django.db import transaction

from plan.scrape.rooms import update_rooms
from plan.common.logger import init_console

init_console()

logger = logging.getLogger()

class Command(BaseCommand):

    @transaction.commit_manually
    def handle(self, *args, **options):
        try:
            update_rooms()

            if raw_input('Save changes? [y/N] ').lower() == 'y':
                transaction.commit()
                print 'Saving changes...'
            else:
                transaction.rollback()
                print 'Ignoring changes...'

        except:
            transaction.rollback()
            raise
