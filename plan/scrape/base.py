# This file is part of the plan timetable generator, see LICENSE for details.

import logging

from django import db

from plan.common.models import (Course, Exam, ExamType, Lecture, LectureType,
                                Lecturer, Group, Room, Semester, Week)
from plan.scrape import utils


class Scraper(object):
    fields = tuple()
    extra_fields = tuple()

    def __init__(self, semester):
        self.semester = semester
        self.seen = []
        self.stats = {'scraped': 0,   # items we have scraped
                      'processed': 0, # items that made it through prepare_data()
                      'persisted': 0, # items that are in db
                      'created': 0,   # items that have been created
                      'updated': 0,   # items we have updated
                      'unaltered': 0, # items we found but did not alter
                      'deleted': 0}   # items we plan to delete

    def scrape(self, semester):
        """Gets data from external source and yields results."""
        raise NotImplementedError

    def queryset(self):
        """Base queryset to use in all scraper operations.

           Needs to limit results to the righ semester and can optionaly order
           the results for more logical display when listing items.
        """
        raise NotImplementedError

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
        for data in self. scrape():
            try:
                self.log_scraped(data)

                data = self.prepare_data(data)
                if not data:
                    continue
                self.log_processed(data)

                kwargs = self.prepare_save(data)
                if not kwargs:
                    continue

                obj, created = self.save(kwargs)
                self.log_persisted(obj)

                if created:
                    self.log_created(obj)
                    continue

                changes = self.update(obj, kwargs['defaults'])
                if changes:
                    self.log_updated(obj, changes)
                    continue

                self.log_unaltered(obj)
            finally:
                db.reset_queries()

        # Note: we don't delete all objects through this query.
        # defult prepare_delete() returns qs.none() to be on the safe side.
        qs = self.prepare_delete()
        self.log_deleted(qs)

        self.log_finished()
        return qs

    def prepare_data(self, data):
        """Clean and/or validate data from scrape method.

           Not returning data will skip the provided data.
        """
        return data

    def prepare_save(self, data):
        """Convert cleaned data into arguments for get_or_create()."""
        kwargs = {'defaults': {}}
        for field in self.fields:
            kwargs[field] = data.get(field, None)
        for field in self.extra_fields:
            if field in data:
                kwargs['defaults'][field] = data[field]
        return kwargs

    def save(self, kwargs):
        """Save prepared arguments using get_or_create().

           This method keeps track of known PKs and ignores these objects when
           creating new ones. Which prevents some cases of stepping on our own
           toes during updates.
        """
        qs = self.queryset().exclude(pk__in=self.seen)
        obj, created = qs.get_or_create(**kwargs)
        return obj, created

    def update(self, obj, defaults):
        """Ensure that obj has up to date values for its fields.

           Returns {field: (old_value, new_value)}.
        """
        changes = {}

        for field, value in extras.items():
            old_value = getattr(obj, field)
            if old_value != value:
                setattr(obj, field, value)
                changes[field] = (old_value, value)

        if changes:
            # TODO(adamcik): use update_fields once we have django 1.5
            obj.save()

        return changes

    def prepare_delete(self):
        """Filter a query set done to objects that should be deleted.

           Default is to delete all items within the current scrapers queryset
           limitation that we have not updated or created.
        """
        return self.queryset().exclude(pk__in=self.seen)

    def display(self, obj):
        """Helper that defines how objects are stringified for display."""
        return unicode(obj)

    def log_scraped(self, data):
        self.stats['scraped'] += 1

    def log_processed(self, data):
        self.stats['processed'] += 1

    def log_persisted(self, obj):
        self.seen.append(obj.pk)
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
    fields = ('code', 'version', 'semester')
    extra_fields = ('name', 'url', 'points')

    def queryset(self):
        qs = Course.objects.filter(semester=self.semester)
        return qs.order_by('code', 'version')

    def prepare_data(self, data):
        data['semester'] = self.semester
        if 'name' in data:
            data['name'] = utils.clean_string(data['name'])
        if 'points' in data:
            data['points'] = utils.clean_decimal(data['points'])
        return data

    def display(self, obj):
        return obj.code


# TODO(adamcik): remove noop that has been added.
class LectureScraper(Scraper):
    fields = ('course', 'day', 'start', 'end', 'type')
    extra_fields = ('rooms', 'lecturers', 'groups', 'weeks')

    def queryset(self):
        qs = Lecture.objects.filter(course__semester=self.semester)
        return qs.order_by('course__code', 'day', 'start')

    def prepare_data(self, data):
        if not data['course'] or not data['start'] or not data['end']:
            return
        elif data['day'] not in dict(Lecture.DAYS):
            return

        data['type'] = self.lecture_type(data['type'])
        data['rooms'] = [self.room(r) for r in data['rooms']]
        data['lecturers'] = [self.lecturer(l) for l in data['lecturers']]
        data['groups'] = [self.group(g) for g in data['groups']]

        if not data['groups']:
            data['groups'] = [self.group(Group.DEFAULT)]

        return data

    def save(self, kwargs):
        kwargs = kwargs.copy()
        defaults = kwargs.pop('defaults')

        groups = set(g.pk for g in defaults['groups'])
        kwargs['type'] = self.lecture_type(kwargs['type'])

        lectures = self.queryset().filter(**kwargs).order_by('id')
        lectures = lectures.exclude(pk__in=self.seen)

        # Try way to hard to find what is likely the same lecture so we can
        # update instead of replacing. This is needed to have some what stable
        # imports and not step on our own feet flip flopping lectures back and
        # forth.
        candidates = {}
        for l in lectures:
            candidates[l] = 0

            if groups == set(l.groups.values_list('pk', flat=True)):
                candidates[l] = 3

            for field in ('rooms', 'lecturers'):
                if set(defaults[field]) == set(getattr(l, field).all()):
                    candidates[l] += 1

            weeks = l.weeks.values_list('number', flat=True)
            if set(defaults['weeks']) == set(weeks):
                candidates[l] += 2

        if candidates:
            obj, score = sorted(candidates.items(), key=lambda i: -i[1])[0]
            if score > 0:
                return obj, False

        obj = lectures.create(**kwargs)
        self.update(obj, defaults)
        return obj, True

    def update(self, obj, defaults):
        changes = {}

        for field in ('rooms', 'lecturers', 'groups'):
            current = set(getattr(obj, field).all())
            if current != set(defaults[field]):
                changes[field] = current, set(defaults[field])
                setattr(obj, field, defaults[field])

        if changes:
            obj.save()

        current = set(obj.weeks.values_list('number', flat=True))
        if current != set(defaults['weeks']):
            changes['weeks'] = current, set(defaults['weeks'])
            obj.weeks.all().delete()

            for week in defaults['weeks']:
                Week.objects.create(lecture=obj, number=week)

        return changes

    def lecture_type(self, name):
        return LectureType.objects.get_or_create(name=name)[0]

    def room(self, name):
        return Room.objects.get_or_create(name=name)[0]

    def lecturer(self, name):
        return Lecturer.objects.get_or_create(name=name)[0]

    def group(self, code):
        return Group.objects.get_or_create(code=code)[0]


class ExamScraper(Scraper):
    fields = ('course', 'type', 'combination', 'exam_date')
    default_fields = ('duration', 'exam_time', 'handout_date', 'handout_time')

    def queryset(self):
        qs = Exam.objects.filter(course__semester=self.semester)
        return qs.order_by('course__code', 'exam_date')

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

    def exam_type(self, code, name):
        exam_type, created = ExamType.objects.get_or_create(
            code=code, defaults={'name': name})

        if exam_type.name != name:
            exam_type.name = name
            exam_type.save()

        return exam_type
