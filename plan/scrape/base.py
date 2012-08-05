# This file is part of the plan timetable generator, see LICENSE for details.

import decimal
import logging

from plan.common.models import Exam, ExamType, Course, Semester


def compare(old, new):
    old_is_string = isinstance(old, basestring)
    new_is_string = isinstance(new, basestring)

    if (new_is_string and old_is_string and new.strip() == old.strip()):
        return '<whitespace>'
    return '[%s] -> [%s]' % (new, old)


class Scraper(object):
    def __init__(self, semester, options):
        self.semester = semester
        self.options = options
        self.stats = {'created': 0,
                      'updated': 0,
                      'deleted': 0}

    def delete(self, items):
        raise NotImplementedError

    def fetch(self, match=None):
        raise NotImplementedError

    def run(self):
        return self.fetch()

    def needs_commit(self):
        return True

    def clean(self, raw_text):
        text = raw_text.strip()
        if text[0] in ('"', "'") and text[0] == text[-1]:
            text = text[1:-1].strip()
        return text


class GenericScraper(Scraper):
    MODEL = None
    FIELDS = tuple()
    CLEAN_FIELDS = tuple()
    DEFAULT_FIELDS = tuple()

    def delete(self, items):
        # TODO(adamcik): figure out related cascade deletes?
        self.MODEL.objects.filter(id__in=[i.id for i in items]).delete()

    def needs_commit(self):
        return (self.stats['created'] > 0 or
                self.stats['updated'] > 0 or
                self.stats['deleted'] > 0)

    def display(self, item):
        return str(item)

    def process_data(self, data):
        return data

    def process_kwargs(self, kwargs, data):
        return kwargs

    def process_remove(self, seen):
        return []

    def run(self):
        semester, created = Semester.objects.get_or_create(
            year=self.semester.year, type=self.semester.type)
        seen = []

        for data in self.fetch():
            # Allow scrapers to modify data before giving it to
            # generic code below.
            data = self.process_data(data)

            # Build kwargs for get or create by:
            #  1. cleaning fields that are in CLEAN_FIELDS
            #  2. adding lookup fields that are in FIELDS
            #  3. adding defaults fields that are in DEFAULT_FIELDS
            kwargs = {'defaults': {}}
            for field in data:
                if field in self.CLEAN_FIELDS:
                    data[field] = self.clean(data[field])

                if field in self.FIELDS:
                    kwargs[field] = data[field]
                elif field in self.DEFAULT_FIELDS:
                    kwargs['defaults'][field] = data[field]

            kwargs = self.process_kwargs(kwargs, data)
            if not kwargs:
                continue

            obj, created = self.MODEL.objects.get_or_create(**kwargs)
            seen.append(obj.id)
            changes = {}

            if created:
                self.stats['created'] += 1
            else:
                # Check if any of the non lookup fields need to be fixed.
                for field, value in kwargs['defaults'].items():
                    old_value = getattr(obj, field)
                    if old_value != value:
                        setattr(obj, field, value)
                        changes[field] = (old_value, value)

            # TODO(adamcik): use update_fields once we have django 1.5
            if changes:
                obj.save()
                self.stats['updated'] += 1

            if created:
                logging.info('Added %s', self.display(obj))
            elif changes:
                logging.info('Updated %s:', self.display(obj))
                for key, (new, old) in changes.items():
                    logging.info('  %s: %s', key, compare(old, new))
            else:
                logging.debug('No changes for %s', self.display(obj))

        remove = list(self.process_remove(seen))
        self.stats['deleted'] = len(remove)
        return remove


class CourseScraper(GenericScraper):
    MODEL = Course
    FIELDS = ('code', 'version', 'semester')
    CLEAN_FIELDS = ('name',)
    DEFAULT_FIELDS = ('name', 'url', 'points')

    def __init__(self, *args, **kwargs):
        super(CourseScraper, self).__init__(*args, **kwargs)
        self.to_delete = []

    def process_data(self, data):
        semester, created = Semester.objects.get_or_create(
            year=self.semester.year, type=self.semester.type)
        data['semester'] = semester
        return data

    def process_kwargs(self, kwargs, data):
        if not data.get('delete', False):
            return kwargs

        try:
            del kwargs['defaults']
            self.to_delete.append(self.MODEL.objects.get(**kwargs))
        except self.MODEL.DoesNotExist:
            pass

    def process_remove(self, seen):
        return self.to_delete

    def display(self, item):
        return item.code


class ExamScraper(GenericScraper):
    MODEL = Exam
    FIELDS = ('course', 'exam_date', 'exam_time',
              'handout_date', 'handout_time')
    DEFAULT_FIELDS = ('duration', 'type')

    # TODO(adamcik): add sanity checking in generic scraper.

    def process_data(self, data):
        if 'duration' in data:
            data['duration'] = decimal.Decimal(data['duration'])

        exam_type, created = ExamType.objects.get_or_create(
            code=data['type__code'], defaults={'name': data['type__name']})
        if exam_type.name != data['type__name']:
            exam_type.name = data['type__name']
            exam_type.save()
        data['type'] = exam_type
