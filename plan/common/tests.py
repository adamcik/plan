import datetime
from copy import copy

from django.test import TestCase

# FIXME test that api limits things to one semester

class MockDatetime(datetime.datetime):
    @classmethod
    def now(cls):
        return datetime.datetime(2009, 1, 1)

class BaseTestCase(TestCase):
    def setUp(self):
        self.datetime = datetime.datetime
        datetime.datetime = MockDatetime

    def tearDown(self):
        datetime.datetime = self.datetime

class EmptyViewTestCase(BaseTestCase):
    def test_index(self):
        response = self.client.get('/')

        self.failUnlessEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'start.html')

    def test_shortcut(self):
        response = self.client.get('/adamcik/')

        self.failUnlessEqual(response.status_code, 404)
        self.assertTemplateUsed(response, '404.html')

class ViewTestCase(BaseTestCase):
    fixtures = ['test_data.json', 'test_user.json']

    def test_index(self):
        from django.core.cache import cache
        from plan.common.cache import clear_cache, get_realm
        from plan.common.models import Semester

        s = Semester.current()

        # Load page
        response = self.client.get('/')
        self.failUnlessEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'start.html')

        # Check that cache gets set
        realm = get_realm(s.year, s.get_type_display())
        stats = cache.get('stats', realm=realm)

        expected_stats = {
            'subscription_count': 5,
            'stats': [
                (2, u'COURSE2', u'Course 2 full name'),
                (2, u'COURSE1', u'Course 1 full name'),
                (1, u'COURSE3', u'Course 3 full name')
            ],
            'slug_count': 2,
            'schedule_form': '<input type="text" name="slug" value="%s" id="id_slug" />\n' + \
                             '<input type="hidden" name="semester" value="1" id="id_semester" />',
            'current': Semester.current(from_db=True),
            'color_map': {},
            'limit': 15,
            'deadline_count': 3
        }

        self.assertEquals(stats, expected_stats)

        # Check that cache gets cleared
        clear_cache(s.year, s.get_type_display(), 'adamcik')
        stats = cache.get('stats', realm=realm)

        self.assertEquals(stats, None)

    def test_shortcut(self):
        from django.core.urlresolvers import reverse
        from plan.common.models import Semester

        s = Semester.current()
        url = reverse('schedule', args=[s.year, s.get_type_display(), 'adamcik'])

        response = self.client.get('/adamcik/')
        self.assertRedirects(response, url)

    def test_schedule(self):
        from django.core.urlresolvers import reverse
        from django.core.cache import cache
        from plan.common.models import Semester
        from plan.common.cache import clear_cache, get_realm

        s = Semester.current()

        for name in ['schedule', 'schedule-advanced']:
            url = reverse(name, args=[s.year, s.get_type_display(), 'adamcik'])

            realm = get_realm(s.year, s.get_type_display(), 'adamcik')

            response = self.client.get(url)
            self.assertTemplateUsed(response, 'schedule.html')

            cache_response = cache.get(url, realm=realm)
            self.assertEquals(response.content, cache_response.content)

            clear_cache(s.year, s.get_type_display(), 'adamcik')
            cache_response = cache.get(url, realm=realm)

            self.assertEquals(cache_response, None)

class TimetableTestCase(BaseTestCase):
    fixtures = ['test_data.json', 'test_user.json']

    def test_timetable(self):
        from plan.common.models import Lecture, Semester
        from plan.common.timetable import Timetable

        lectures = Lecture.objects.get_lectures(2009, Semester.SPRING, 'adamcik')

        timetable = Timetable(lectures)
        timetable.place_lectures()

        rows = []

        lectures  = dict([(l.id, l) for l in lectures])
        lecture2  = {'lecture': lectures[2],  'rowspan': 2,  'remove': False}
        lecture3  = {'lecture': lectures[3],  'rowspan': 2,  'remove': False}
        lecture4  = {'lecture': lectures[4],  'rowspan': 6,  'remove': False}
        lecture5  = {'lecture': lectures[5],  'rowspan': 2,  'remove': False}
        lecture8  = {'lecture': lectures[8],  'rowspan': 1,  'remove': False}
        lecture9  = {'lecture': lectures[9],  'rowspan': 12, 'remove': False}
        lecture10 = {'lecture': lectures[10], 'rowspan': 1,  'remove': False}
        lecture11 = {'lecture': lectures[11], 'rowspan': 1,  'remove': False}

        rows.append([[lecture2, lecture4, {}],       [lecture9], [lecture10], [{}], [{}]])

        lecture2 = copy(lecture2)
        lecture2['remove'] = True
        lecture9 = copy(lecture9)
        lecture9['remove'] = True

        lecture4 = copy(lecture4)
        lecture4['remove'] = True

        rows.append([[lecture2, lecture4, lecture5], [lecture9], [{}], [{}], [{}]])

        lecture5 = copy(lecture5)
        lecture5['remove'] = True

        rows.append([[lecture3, lecture4, lecture5], [lecture9], [{}], [{}], [{}]])

        lecture3 = copy(lecture3)
        lecture3['remove'] = True

        rows.append([[lecture3, lecture4, {}],       [lecture9], [{}], [{}], [{}]])
        rows.append([[{},       lecture4, {}],       [lecture9], [{}], [{}], [{}]])
        rows.append([[{},       lecture4, {}],       [lecture9], [{}], [{}], [{}]])
        rows.append([[{},       {},       {}],       [lecture9], [{}], [{}], [{}]])
        rows.append([[lecture8, {},       {}],       [lecture9], [{}], [{}], [{}]])
        rows.append([[{},       {},       {}],       [lecture9], [{}], [{}], [{}]])
        rows.append([[{},       {},       {}],       [lecture9], [{}], [{}], [{}]])
        rows.append([[{},       {},       {}],       [lecture9], [{}], [{}], [{}]])
        rows.append([[{},       {},       {}],       [lecture9], [lecture11], [{}], [{}]])

        for t,r in zip(timetable.table, rows):
            self.assertEquals(t,r)

class ManagerTestCase(BaseTestCase):
    fixtures = ['test_data.json', 'test_user.json']

    def test_get_lectures(self):
        from plan.common.models import Lecture, Semester

        # Exclude lectures connected to other courses and excluded from userset
        control = Lecture.objects.exclude(id__in=[6,7])

        # Try showing all lectures
        lectures = Lecture.objects.get_lectures(2009, Semester.SPRING, 'adamcik')
        lectures = filter(lambda l: l.show_week and not l.exclude, lectures)
        self.assertEquals(set(lectures), set(control))

        # Try showing only lectures in week 1
        lectures = Lecture.objects.get_lectures(2009, Semester.SPRING, 'adamcik', 1)
        lectures = filter(lambda l: l.show_week and not l.exclude, lectures)
        self.assertEquals(set(lectures), set(control.filter(weeks__number=1)))

        # Try showing lectures in week 2
        lectures = Lecture.objects.get_lectures(2009, Semester.SPRING, 'adamcik', 2)
        lectures = filter(lambda l: l.show_week and not l.exclude, lectures)
        self.assertEquals(set(lectures), set(control.filter(weeks__number=2)))

        # Try lectures in week 3, ie none
        lectures = Lecture.objects.get_lectures(2009, Semester.SPRING, 'adamcik', 3)
        lectures = filter(lambda l: l.show_week and not l.exclude, lectures)
        self.assertEquals(set(lectures), set())

    def test_get_deadlines(self):
        from plan.common.models import Deadline, Semester

        control = Deadline.objects.filter(id__in=[1,2])

        deadlines = Deadline.objects.get_deadlines(2009, Semester.SPRING, 'adamcik')
        self.assertEquals(set(deadlines), set(control))

    def test_get_exams(self):
        from plan.common.models import Exam, Semester

        exams = Exam.objects.get_exams(2009, Semester.SPRING, 'adamcik')
        self.assertEquals(set(exams), set(Exam.objects.exclude(id__in=[3,4])))

    def test_get_courses(self):
        from plan.common.models import Course, Semester

        courses = Course.objects.get_courses(2009, Semester.SPRING, 'adamcik')
        self.assertEquals(set(courses), set(Course.objects.exclude(id=4)))

    def test_get_courses_with_exams(self):
        from plan.common.models import Course, Semester

        courses = Course.objects.get_courses_with_exams(2009, Semester.SPRING)
        courses = map(lambda a: a[0], courses)

        # Ensure that courses without exams are included and courses with
        # multiple exams on time per exam
        self.assertEquals(courses, [1, 2, 3, 4, 4])

    def test_get_usersets(self):
        from plan.common.models import UserSet, Semester

        control = UserSet.objects.filter(id__in=[1,2,3])
        usersets = UserSet.objects.get_usersets(2009, Semester.SPRING, 'adamcik')
        self.assertEquals(set(control), set(usersets))

class UtilTestCase(BaseTestCase):
    fixtures = ['test_data.json']

    def test_colormap(self):
        from plan.common.utils import ColorMap

        c = ColorMap()
        keys = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 3, 5, 6]
        for k in keys:
            self.assertEquals(c[k], 'color%d' % (k % c.max))

        c = ColorMap(hex=True)
        for k in keys:
            self.assertEquals(c[k], c.colors[k % c.max])

        self.assertEquals(c[None], '')

    def test_compact_sequence(self):
        from plan.common.utils import compact_sequence

        seq = compact_sequence([1, 2, 3, 5, 6, 7, 8, 12, 13, 15, 17, 19])
        self.assertEquals(seq, ['1-3', '5-8', '12-13', '15', '17', '19'])

        seq = compact_sequence([1, 2, 3])
        self.assertEquals(seq, ['1-3'])

        seq = compact_sequence([1, 3])
        self.assertEquals(seq, ['1', '3'])

        seq = compact_sequence([])
        self.assertEquals(seq, [])

class FormTestCase(BaseTestCase):
    pass
