# This file is part of the plan timetable generator, see LICENSE for details.

import collections
import datetime
import logging
import HTMLParser

from django import db
from django.db.models import Count

from plan.common.models import (Course, Exam, ExamType, Lecture, LectureType,
                                Lecturer, Location, Group, Room, Semester, Week)
from plan.scrape import utils


html_parser = HTMLParser.HTMLParser()


class Scraper(object):
    fields = ()
    extra_fields = ()
    m2m_fields = ()

    def __init__(self, semester, course_prefix=None):
        self.semester = semester
        self.course_prefix = course_prefix
        self.import_time = datetime.datetime.now()
        self.stats = collections.OrderedDict([
            ('initial',  0),  # items initialy in db
            ('scraped',  0),  # items we have scraped
            ('processed', 0), # items that made it through prepare_data()
            ('persisted', 0), # items that are in db
            ('created', 0),   # items that have been created
            ('updated', 0),   # items we have updated
            ('unaltered', 0), # items we found but did not alter
            ('deleted', 0),   # items we plan to delete
            ('final', 0),     # items left in db after scrape+delete
        ])

    def scrape(self, semester):
        """Gets data from external source and yields results."""
        raise NotImplementedError

    def queryset(self):
        """Base queryset to use in all scraper operations.

           Needs to limit results to the righ semester and can optionaly order
           the results for more logical display when listing items.
        """
        raise NotImplementedError

    def should_proccess_course(self, code):
        # TODO: delete as this is no longer called?
        """Common helper for filtering out course codes to skip."""
        return not self.course_prefix or code.startswith(self.course_prefix)

    def format(self, items):
        """Format list of items."""
        return utils.columnify(items)

    def needs_commit(self, stats=None):
        """Indicate if there are any changes that need to be saved.

           Can be called via super() when overriden with other fields.
        """
        for name in (stats or ('created', 'updated', 'deleted')):
            if self.stats.get(name, 0) > 0:
                return True
        return False

    def prefetch(self):
        self.log_initial()
        for data in self.scrape():
            self.log_scraped(data)
        self.log_stats()
        return False

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
        self.log_initial()

        for data in self.scrape():
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

                changes = self.update_m2m(obj, data)

                if created:
                    self.log_created(obj)
                    continue

                changes.update(self.update(obj, kwargs['defaults']))

                if changes:
                    self.log_updated(obj, changes)
                    continue

                self.log_unaltered(obj)
            finally:
                db.reset_queries()

        self.delete(self.prepare_delete())
        self.log_stats()

        return self.needs_commit()

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

           This method keeps filters out already updated items. Which prevents
           some cases of stepping on our own toes during updates.
        """
        qs = self.queryset().filter(last_import__lt=self.import_time)
        return qs.get_or_create(**kwargs)

    def update_m2m(self, obj, data):
        changes = {}
        for field in self.m2m_fields:
            new_values = data[field]
            old_values = list(getattr(obj, field).all())

            if set(new_values) != set(old_values):
                getattr(obj, field).set(new_values)
                changes[field] = (old_values, new_values)
        return changes

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

        obj.save()  # To trigger update of last import time.
        return changes

    def prepare_delete(self):
        """Filter a query set done to objects that should be deleted.

           Default is to delete all items within the current scrapers queryset
           limitation that we have not updated or created.
        """
        return self.queryset().filter(last_import__lt=self.import_time)

    def delete(self, qs):
        """Actually delete the query set."""
        self.log_delete(qs)
        qs.delete()

    def display(self, obj):
        """Helper that defines how objects are stringified for display."""
        return unicode(obj)

    def log_initial(self):
        self.stats['initial'] = self.queryset().count()

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

    def log_delete(self, qs):
        self.stats['deleted'] = qs.count()
        if qs:
            logging.info('Deleted:\n%s', self.format(qs))

    def log_stats(self):
        self.stats['final'] = self.queryset().count() - self.stats['deleted']

        values = []
        for key, value in self.stats.items():
            values.append('%s: %s' % (key.title(), value))
        logging.warning(', '.join(values))

    def log_extra(self, field, msg=None, args=None, count=0):
        self.stats[field] = self.stats.get(field, 0) + count
        if msg:
            logging.info(msg, *(args or []))


# TODO(adamcik): add constraint for code+semester to prevent multiple versions
# by mistake
class CourseScraper(Scraper):
    fields = ('code', 'version', 'semester')
    extra_fields = ('name', 'url', 'points')
    m2m_fields = ('locations',)

    def queryset(self):
        qs = Course.objects.filter(semester=self.semester)
        if self.course_prefix:
            qs = qs.filter(code__startswith=self.course_prefix)
        qs = qs.annotate(Count('lecture'))
        return qs.order_by('code', 'version')

    def prepare_data(self, data):
        data['semester'] = self.semester
        if 'name' in data:
            data['name'] = utils.clean_string(data['name'])
        if 'points' in data:
            data['points'] = utils.clean_decimal(data['points'])

        locations, data['locations'] = data['locations'][:], []
        for name in locations:
            data['locations'].append(self.location(utils.clean_string(name)))

        return data

    def display(self, obj):
        return obj.code

    def format(self, items):
        return utils.columnify(
            (u'%s - %s lectures' % (c, c.lecture__count) for c in items), 2)

    def location(self, name):
        return Location.objects.get_or_create(name=name)[0]


class LectureScraper(Scraper):
    # TODO: should we unhide lectures that get modified?
    fields = ('course', 'day', 'start', 'end', 'type')
    extra_fields = ('rooms', 'lecturers', 'groups', 'weeks', 'title')

    def queryset(self):
        qs = Lecture.objects.filter(course__semester=self.semester)
        if self.course_prefix:
            qs = qs.filter(course__code__startswith=self.course_prefix)
        qs = qs.annotate(Count('course__subscription'))
        return qs.order_by('course__code', 'day', 'start')

    def course_queryset(self):
        qs = Course.objects.filter(semester=self.semester)
        if self.course_prefix:
            qs = qs.filter(code__startswith=self.course_prefix)
        return qs.order_by('code', 'version')

    def format(self, items):
        return utils.columnify(
            (u'%s - %s subscriptions' % (c, c.course__subscription__count) for c in items), 2)

    def needs_commit(self, stats=None):
        return super(LectureScraper, self).needs_commit(
            ('created', 'updated', 'deleted', 'rooms'))

    def prepare_data(self, data):
        if not data['course'] or not data['start'] or not data['end']:
            return
        elif data['day'] not in dict(Lecture.DAYS):
            return

        data['lecturers'] = utils.clean_list(data['lecturers'], utils.clean_string)
        data['groups'] = utils.clean_list(data['groups'], utils.clean_string)

        rooms, data['rooms'] = data['rooms'][:], []
        for code, name, url in rooms:
            code = utils.clean_string(code)
            name = utils.clean_string(name)
            if code or name:
                data['rooms'].append(self.room(code, name, url))

        data['type'] = self.lecture_type(data['type'])
        # TODO: Handle url in addition to names?
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
        lectures = lectures.filter(last_import__lt=self.import_time)

        # Try way to hard to find what is likely the same lecture so we can
        # update instead of replacing. This is needed to have some what stable
        # imports and not step on our own feet flip flopping lectures back and
        # forth.
        # TODO: add an external_id field to use when available.
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

        # TODO: Replace with m2m_fields handling?
        for field in ('rooms', 'lecturers', 'groups'):
            current = set(getattr(obj, field).all())
            if current != set(defaults[field]):
                changes[field] = current, set(defaults[field])
                setattr(obj, field, defaults[field])

        if obj.title != defaults['title']:
            changes['title'] = (obj.title, defaults['title'])
            obj.title = defaults['title']

        obj.save()

        current = set(obj.weeks.values_list('number', flat=True))
        if current != set(defaults['weeks']):
            changes['weeks'] = current, set(defaults['weeks'])
            obj.weeks.all().delete()

            for week in defaults['weeks']:
                Week.objects.create(lecture=obj, number=week)
            # TODO: delete exclusions if the weeks changed?
            # obj.excluded_fromc.clear()

        return changes

    def lecture_type(self, name):
        return LectureType.objects.get_or_create(name=name)[0]

    def room(self, code, name, url):
        if url and '&amp;' in url:
            url = html_parser.unescape(url)

        if code:
            try:
                room = Room.objects.get(code=code)
                if room.name != name:
                    logging.warning('Room %s: %s != %s', room.code, room.name, name)
                if utils.valid_url(url) and room.url != url:
                    self.log_extra('rooms', 'Adding room url %s to %s (%s)', [url, room.name, room.code])
                    room.url = url
                    room.save()
                return room
            except Room.DoesNotExist:
                pass

        # Get room by just name and code=None so we can try and upgrade.
        rooms = Room.objects.filter(code=None, name=name)
        if len(rooms) == 1:
            r = rooms.get()
            if code:
                self.log_extra('rooms', 'Adding room code %s to %s', [code, r.name])
                r.code = code
                r.save()
            if url and url != r.url:
                self.log_extra('rooms', 'Adding room url %s to %s', [url, r.name])
                r.url = url
                r.save()
            return r

        if not code:
            return Room.objects.get_or_create(name=name)[0]
        return Room.objects.get_or_create(code=code, defaults={'name': name})[0]

    def lecturer(self, name):
        return Lecturer.objects.get_or_create(name=name)[0]

    def group(self, code):
        return Group.objects.get_or_create(code=code)[0]


class ExamScraper(Scraper):
    fields = ('course', 'type', 'combination', 'exam_date')
    extra_fields = ('duration', 'exam_time', 'handout_date', 'handout_time')

    def queryset(self):
        qs = Exam.objects.filter(course__semester=self.semester)
        if self.course_prefix:
            qs = qs.filter(course__code__startswith=self.course_prefix)
        return qs.order_by('course__code', 'exam_date')

    def course_queryset(self):
        qs = Course.objects.filter(semester=self.semester)
        if self.course_prefix:
            qs = qs.filter(code__startswith=self.course_prefix)
        return qs.order_by('code', 'version')

    def prepare_data(self, data):
        # TODO(adamcik): consider not hardcoding these.
        if self.semester.type == self.semester.SPRING:
            start = datetime.date(self.semester.year, 1, 1)
            end = datetime.date(self.semester.year, 6, 30)
        else:
            start = datetime.date(self.semester.year, 7, 1)
            end = datetime.date(self.semester.year, 12, 31)

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


class RoomScraper(Scraper):
    fields = ('code',)
    extra_fields = ('name', 'url',)

    def queryset(self):
        return Room.objects.order_by('name', 'code')

    def delete(self, qs):
        logging.warning('This scraper newer deletes any rooms as we would '
                        'loose data we can\'t get back.')


class SyllabusScraper(Scraper):
    fields = ('code',)
    extra_fields = ('syllabus',)

    def queryset(self):
        qs = Course.objects.filter(semester=self.semester)
        if self.course_prefix:
            qs = qs.filter(code__startswith=self.course_prefix)
        return qs.order_by('code', 'version')

    def display(self, obj):
        return obj.code

    def prepare_data(self, data):
        # Only update courses we already know about.
        qs = self.queryset().filter(code=data['code'])
        if qs.filter(last_import__lt=self.import_time):
            return data
        elif qs:
            logging.warning('Duplicate syllabus info for: %s', data['code'])

    def delete(self, qs):
        return
        self.log_delete(qs)
        qs.update(syllabus=None)
