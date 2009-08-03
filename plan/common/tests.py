from datetime import datetime
from copy import copy

from django.test import TestCase
from django.core.urlresolvers import reverse
from django.utils.datastructures import MultiValueDict

from plan.common.models import Semester, Group, UserSet, Lecture
from plan.common.cache import get_realm, clear_cache, cache

# FIXME test that api limits things to one semester
# FIXME test get_stats

class BaseTestCase(TestCase):

    def setUp(self):
        from plan.common import models, views
        models.now = lambda: datetime(2009, 1, 1)
        views.now = lambda: datetime(2009, 1, 1)

        self.semester = Semester.current()

        self.realm = get_realm(self.semester, 'adamcik')
        self.default_args = [
                self.semester.year,
                self.semester.get_type_display(),
                'adamcik'
            ]

    def url(self, name, *args):
        if args:
            return reverse(name, args=args)
        else:
            return reverse(name, args=self.default_args)

    def url_basic(self, name):
        return reverse(name)

    def clear(self, ):
        clear_cache(self.semester, 'adamcik')

    def get(self, key):
        return cache.get(key, realm=self.realm)

class EmptyViewTestCase(BaseTestCase):
    def test_index(self):
        response = self.client.get(self.url_basic('frontpage'))

        self.failUnlessEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'start.html')

    def test_shortcut(self):
        response = self.client.get(self.url('shortcut', 'adamcik'))

        self.failUnlessEqual(response.status_code, 404)
        self.assertTemplateUsed(response, '404.html')

class ViewTestCase(BaseTestCase):
    fixtures = ['test_data.json', 'test_user.json']

    # FIXME check what happens when we do GET against change functions

    def test_index(self):
        # Load page
        response = self.client.get(self.url_basic('frontpage'))
        self.failUnlessEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'start.html')

        # Check that cache gets set
        realm = get_realm(self.semester)
        cached_response = cache.get('frontpage', realm=realm)

        self.assertEquals(True, cached_response is not None)
        self.assertEquals(response.content, cached_response.content)

        # Check that cache gets cleared
        self.clear()
        cached_response = cache.get('frontpage', realm=realm)

        self.assertEquals(cached_response, None)

        semester = self.semester
        args = [semester.year, semester.get_type_display()]
        response = self.client.get(self.url('frontpage-semester', *args))
        self.failUnlessEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'start.html')

        # FIXME test posting to index
        # FIXME test missing code 76

    def test_shortcut(self):
        response = self.client.get(self.url('shortcut', 'adamcik'))
        self.assertRedirects(response, self.url('schedule'))

    def test_schedule(self):
        # FIXME add group help testing
        # FIXME courses without lectures
        # FIXME test next semester message
        # FIXME test cache time for deadlines etc
        # FIXME test group-help message

        s = self.semester

        week = 1
        for name in ['schedule', 'schedule-advanced', 'schedule-week', 'schedule-week', 'schedule-all']:
            args = [s.year, s.get_type_display(), 'adamcik']

            if name.endswith('week'):
                args.append(week)
                week += 1

            if name in ['schedule', 'schedule-all']:
                week = 1
                args.append(week)
                name = 'schedule-week'

            url = self.url(name, *args)

            response = self.client.get(url)
            self.assertEquals(response.status_code, 200)
            self.assertTemplateUsed(response, 'schedule.html')

            # Check twice to test cache code 
            response = self.client.get(url)
            self.assertEquals(response.status_code, 200)

            cache_response = self.get(url)
            self.assertEquals(response.content, cache_response.content)

            self.clear()
            cache_response = self.get(url)

            self.assertEquals(cache_response, None)

    def test_course_list(self):
        # FIXME test POST

        s = Semester.current()
        url = self.url('course-list')
        key = '/'.join([str(s.year), s.get_type_display(), 'courses'])

        response = self.client.get(url)
        self.failUnlessEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'course_list.html')

        cache_response = cache.get(key, prefix=True)
        self.assertEquals(response.content, cache_response.content)

        self.clear()
        cache_response = cache.get(key, prefix=True)

        self.assertEquals(response.content, cache_response.content)

    def test_change_course(self):
        # FIXME test semester does not exist
        # FIXME test ie handling
        # FIXME test invalid course
        # FIXME test more that 20 warning
        # FIXME test group-help
        # FIXME test error.html

        original_url = self.url('schedule-advanced')
        url = self.url('change-course')

        post_data = [
            {'submit_add': True,
             'course_add': 'COURSE4'},
            {'submit_name': True,
             '4-name': 'foo'},
            {'submit_name': True,
             '4-name': 'foo bar baz foo bar baz foo bar baz ' + \
                       'foo bar baz foo bar baz foo bar baz'},
            {'submit_remove': True,
             'course_remove': 4},
        ]

        usersets = list(UserSet.objects.filter(slug='adamcik').order_by('id').values_list())

        for data in post_data:
            original_response = self.client.get(original_url)

            response = self.client.post(url, data)

            self.assertEquals(response.status_code, 302)
            self.assert_(response['Location'].endswith(original_url))

            cache_response = self.get(original_url)
            self.assertEquals(cache_response, None)

            response = self.client.get(original_url)
            self.assert_(original_response.content != response.content)

            self.clear()

            new_usersets = list(UserSet.objects.filter(slug='adamcik').order_by('id').values_list())
            self.assert_(new_usersets != usersets)

            usersets = new_usersets

    def test_change_groups(self):
        # FIXME test for courses without groups

        original_url = self.url('schedule-advanced')
        url = self.url('change-groups')

        post_data = [
            {'1-groups': '1',
             '2-groups': '',
             '3-groups': '2'},
            {'1-groups': '',
             '2-groups': '',
             '3-groups': ''},
            {'1-groups': ('1','2'),
             '2-groups': '',
             '3-groups': '2'}
        ]

        groups = list(Group.objects.filter(userset__slug='adamcik').order_by('id').values_list())

        for data in post_data:
            original_response = self.client.get(original_url)

            response = self.client.post(url, MultiValueDict(data))

            self.assert_(response['Location'].endswith(original_url))
            self.assertEquals(response.status_code, 302)

            cache_response = self.get(original_url)
            self.assertEquals(cache_response, None)

            response = self.client.get(original_url)
            self.assert_(original_response.content != response.content)

            self.clear()

            new_groups = list(Group.objects.filter(userset__slug='adamcik').order_by('id').values_list())
            self.assert_(groups != new_groups)

            groups = new_groups


    def test_change_lectures(self):
        # FIXME test nulling out excludes

        original_url = self.url('schedule-advanced')
        url = self.url('change-lectures')

        post_data = [
            {'exclude': ('2', '3', '8')},
            {'exclude': ('2')},
            #{}, # FIXME add to test
            {'exclude': ('2', '3', '8', '9', '7', '10', '11', '4', '5', '6')},
            {'exclude': ('2')},
            {'exclude': ('2', '3', '8')},
        ]

        lectures = list(Lecture.objects.filter(excluded_from__slug='adamcik').order_by('id').values_list())

        for data in post_data:
            original_response = self.client.get(original_url)

            response = self.client.post(url, MultiValueDict(data))

            self.assert_(response['Location'].endswith(original_url))
            self.assertEquals(response.status_code, 302)

            cache_response = self.get(original_url)
            self.assertEquals(cache_response, None)

            response = self.client.get(original_url)
            self.assert_(original_response.content != response.content)

            self.clear()

            new_lectures = list(Lecture.objects.filter(excluded_from__slug='adamcik').order_by('id').values_list())
            self.assert_(lectures != new_lectures)

            lectures = new_lectures

    def test_new_deadline(self):
        pass
        # FIXME

    def test_copy_deadlines(self):
        pass
        # FIXME

class TimetableTestCase(BaseTestCase):
    fixtures = ['test_data.json', 'test_user.json']

    def test_timetable(self):
        # FIXME test expansion
        # FIXME test instert times
        # FIXME test map_to_slot

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

class MiddlewaresTestCase(BaseTestCase):
    pass

    # FIXME test InternalIpMiddleware
    # FIXME test UserBasedExceptionMiddleware

class ModelsTestCase(BaseTestCase):
    pass

    # FIXME test unicode
    # FIXME test course.get_url
    # FIXME test get_stats(int)
    # FIXME test semester.init customisation
    # FIXME test get_first and last day
    # FIXME test semester.next and get_weeks
    # FIXME test semester.current
    # FIXME test deadline.get_datetime
    # FIXME test deadline.get_slug
    # FIXME test deadline.get_course

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
        self.assertEquals(courses, [1, 1, 1, 1, 2, 3, 4, 4])

    def test_get_usersets(self):
        from plan.common.models import UserSet, Semester

        control = UserSet.objects.filter(id__in=[1,2,3])
        usersets = UserSet.objects.get_usersets(2009, Semester.SPRING, 'adamcik')
        self.assertEquals(set(control), set(usersets))

class UtilTestCase(BaseTestCase):
    fixtures = ['test_data.json']

    def test_colormap(self):
        from plan.common.utils import ColorMap, COLORS

        c = ColorMap()
        keys = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 3, 5, 6]
        for k in keys:
            self.assertEquals(c[k], 'color%d' % (k % c.max))

        c = ColorMap(hex=True)
        for k in keys:
            self.assertEquals(c[k], COLORS[k % c.max])

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
