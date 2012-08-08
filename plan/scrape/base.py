# This file is part of the plan timetable generator, see LICENSE for details.

import logging

from plan.common.models import Course, Exam, ExamType, Lecture, Semester
from plan.scrape import utils


class Scraper(object):
    model = None
    fields = tuple()
    default_fields = tuple()
    create_semester = False

    def __init__(self, semester):
        self.semester = semester
        self.stats = {'scraped': 0,   # items we have scraped
                      'processed': 0, # items that made it through prepare_data()
                      'persisted': 0, # items that are in db
                      'created': 0,   # items that have been created
                      'updated': 0,   # items we have updated
                      'unaltered': 0, # items we found but did not alter
                      'deleted': 0}   # items we plan to delete

    @property
    def needs_commit(self):
        """Indicate if there are any changes that need to be saved.

           If you override run() or otherwise don't update stats you should
           replace this with `needs_commit = True` on your scraper
        """
        return (self.stats['created'] > 0 or
                self.stats['updated'] > 0 or
                self.stats['deleted'] > 0)

    def run(self):
        """Entry point for generic scrape managment command.

           This method will:
           1. Get data by calling scrape()
           2. Process data with prepare_data(), this can be adding, cleaning or
              invalidating data.
           3. Convert data to get_or_create() arguments using prepare_save()
           4. Lookup object, and update it or create a new object.
           5. Call prepare_delete() to determine what to delete.

           This method can be overriden to implement custom scrape logic that
           does not match this pattern.
        """
        pks = []
        for data in self. scrape():
            self.log_scraped(data)

            data = self.prepare_data(data)
            if not data:
                continue
            self.log_processed(data)

            kwargs = self.prepare_save(data, self.fields, self.default_fields)
            if not kwargs:
                continue

            obj, created = self.save(kwargs, self.model, pks)
            self.log_persisted(obj)

            if created:
                self.log_created(obj)
                continue

            changes = self.update(obj, kwargs['defaults'])
            if changes:
                self.log_updated(obj, changes)
                continue

            self.log_unaltered(obj)

        # Note: we don't delete all objects through this query.
        # defult prepare_delete() returns qs.none() to be on the safe side.
        qs = self.prepare_delete(self.model.objects.all(), pks)
        self.log_deleted(qs)

        self.log_finished()
        return qs

    def scrape(self, semester):
        """Gets data from external source and yields results."""
        raise NotImplementedError

    def prepare_data(self, data):
        """Clean and/or validate data from scrape method.

           Not returning data will skip the provided data.
        """
        return data

    def prepare_save(self, data, fields, default_fields):
        """Convert cleaned data into arguments for get_or_create()."""
        kwargs = {'defaults': {}}
        for field in fields:
            kwargs[field] = data.get(field, None)
        for field in default_fields:
            if field in data:
                kwargs['defaults'][field] = data[field]
        return kwargs

    def save(self, kwargs, model, pks):
        """Save prepared arguments using get_or_create().

           This method keeps track of known PKs and ignores these objects when
           creating new ones. Which prevents some cases of stepping on our own
           toes during updates.
        """
        qs = model.objects.exclude(pk__in=pks)
        obj, created = qs.get_or_create(**kwargs)
        pks.append(obj.pk)
        return obj, created

    def update(self, obj, defaults):
        """Ensure that obj has up to date values for its fields.

           Returns {field: (old_value, new_value)}.
        """
        changes = {}

        for field, value in defaults.items():
            old_value = getattr(obj, field)
            if old_value != value:
                setattr(obj, field, value)
                changes[field] = (old_value, value)

        if changes:
            # TODO(adamcik): use update_fields once we have django 1.5
            obj.save()

        return changes

    def prepare_delete(self, qs, pks):
        """Filter a query set done to objects that should be deleted.

           Default is to return `qs.none()` for safety. Actual use should
           filter to only items for the current semester and probably exclude
           items with a PK in `pks`.
        """
        return qs.none()

    def display(self, obj):
        """Helper that defines how objects are stringified for display."""
        return str(obj)

    def log_scraped(self, data):
        self.stats['scraped'] += 1

    def log_processed(self, data):
        self.stats['processed'] += 1

    def log_persisted(self, obj):
        self.stats['persisted'] += 1

    def log_created(self, obj):
        self.stats['created'] += 1
        logging.info('Added %s', self.display(obj))

    def log_updated(self, obj, changes):
        self.stats['updated'] += 1
        logging.info('Updated %s:', self.display(obj))
        for key, (old, new) in changes.items():
            logging.info('  %s: %s', key, utils.compare(old, new))

    def log_unaltered(self, obj):
        self.stats['unaltered'] += 1

    def log_deleted(self, qs):
        self.stats['deleted'] = qs.count()

    def log_finished(self):
        logging.info(('Created: {created} Updated: {updated} Unaltered: '
                      '{unaltered} Deleted: {deleted}').format(**self.stats))


# TODO(adamcik): add constraint for code+semester to prevent multiple versions
# by mistake
class CourseScraper(Scraper):
    model = Course
    fields = ('code', 'version', 'semester')
    default_fields = ('name', 'url', 'points')
    create_semester = True

    def prepare_data(self, data):
        data['semester'] = self.semester
        if 'name' in data:
            data['name'] = utils.clean_string(data['name'])
        if 'points' in data:
            data['points'] = utils.clean_decimal(data['points'])
        return data

    def prepare_delete(self, qs, pks):
        qs = qs.filter(semester=self.semester)
        qs = qs.exclude(pk__in=pks)
        return qs.order_by('code', 'version')

    def display(self, obj):
        return obj.code


# TODO(adamcik): remove noop that has been added.
class LectureScraper(Scraper):
    model = Lecture

    def prepare_data(self, data):
        print data


class ExamScraper(Scraper):
    model = Exam
    fields = ('course', 'type', 'combination', 'exam_date')
    default_fields = ('duration', 'exam_time', 'handout_date', 'handout_time')

    def prepare_data(self, data):
        # TODO(adamcik): do date and time parsing here instead?
        start = self.semester.get_first_day().date()
        end = self.semester.get_last_day().date()
        course = data['course']
        date = data['exam_date']

        if 'duration' in data:
            data['duration'] = utils.clean_decimal(data['duration']) or None

        if not date:
            logging.debug('Date missing for %s', course.code)
        elif not (start <= date <= end):
            logging.debug('Bad date %s for %s', date, course.code)
        else:
            return data

    def prepare_delete(self, qs, pks):
        qs = qs.filter(course__semester=self.semester)
        qs = qs.exclude(pk__in=pks)
        return qs.order_by('course__code', 'exam_date')

    def exam_type(self, code, name):
        exam_type, created = ExamType.objects.get_or_create(
            code=code, defaults={'name': name})

        if exam_type.name != name:
            exam_type.name = name
            exam_type.save()

        return exam_type
