from optparse import make_option

from django.core.management.base import BaseCommand
from django.db import transaction

from plan.scrape.studweb import update_exams
from plan.common.models import Exam, Semester

class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
            make_option('-y', '--year', action='store', dest='year'),
            make_option('-s', '--spring', action='store_const', dest='type', const=Semester.SPRING),
            make_option('-f', '--fall', action='store_const', dest='type', const=Semester.FALL),
            make_option('-d', '--delete', action='store_const', dest='delete', const=1),
        )

    @transaction.commit_manually
    def handle(self, *args, **options):
        semester = Semester.current()

        if options['year'] is not None:
            semester.year = options['year']

        if options['type'] is not None:
            semester.type = options['type']

        to_delete = update_exams(semester.year, semester.type)

        buffer = []
        for l in to_delete:
            if len(buffer) != 3:
                buffer.append(str(l).ljust(35)[:34])
            else:
                print ' - '.join(buffer)
                buffer = []

        if buffer:
            print ' - '.join(buffer)

        if options['delete'] or raw_input('Delete? [y/N] ').lower() == 'y':
            to_delete.delete()

        if raw_input('Save changes? [y/N] ').lower() == 'y':
            transaction.commit()
        else:
            transaction.rollback()
