# This file is part of the plan timetable generator, see LICENSE for details.

from django.utils.datastructures import MultiValueDict
from django.core.urlresolvers import reverse

from plan.common.tests.base import BaseTestCase
from plan.common.models import Semester, Group, Subscription, Lecture, Deadline

class EmptyViewTestCase(BaseTestCase):
    def test_index(self):
        response = self.client.get(self.url_basic('frontpage'))

        self.failUnlessEqual(response.status_code, 404)
        self.assertTemplateUsed(response, '404.html')

    def test_shortcut(self):
        response = self.client.get(self.url('shortcut', 'adamcik'))

        self.failUnlessEqual(response.status_code, 404)
        self.assertTemplateUsed(response, '404.html')

class ViewTestCase(BaseTestCase):
    fixtures = ['test_data.json', 'test_user.json']

    # FIXME check what happens when we do GET against change functions
    # FIXME test adding course that does not exist for a given semester

    def test_index(self):
        response = self.client.get(reverse('frontpage'))
        url = reverse('semester', args=[2010, Semester.SPRING])
        self.assertRedirects(response, url)

    def test_shortcut(self):
        response = self.client.get(self.url('shortcut', 'adamcik'))
        url = reverse('schedule', args=[2010, Semester.SPRING, 'adamcik'])
        self.assertRedirects(response, url)

    def test_schedule_current(self):
        response = self.client.get(self.url('schedule-current'))

        self.assertRedirects(response, reverse('schedule-week',
            args=[self.semester.year, self.semester.type, 'adamcik', '1']))

        response = self.client.get(reverse('schedule-current',
            args=[2009, Semester.FALL, 'adamcik']))

        self.assertRedirects(response, reverse('schedule',
            args=[2009, Semester.FALL, 'adamcik']))

    def test_schedule(self):
        # FIXME add group help testing
        # FIXME courses without lectures
        # FIXME test next semester message
        # FIXME test group-help message

        s = self.semester

        week = 1
        for name in ['schedule', 'schedule-advanced', 'schedule-week', 'schedule-week', 'schedule-all']:
            args = [s.year, s.type, 'adamcik']

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

    def test_course_list(self):
        # FIXME test POST

        s = Semester.current()
        url = self.url('course-list')
        key = '/'.join([str(s.year), s.type, 'courses'])

        response = self.client.get(url)
        self.failUnlessEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'course_list.html')

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
             '4-alias': 'foo'},
            {'submit_name': True,
             '4-alias': 'foo bar baz foo bar baz foo bar baz ' + \
                       'foo bar baz foo bar baz foo bar baz'},
            {'submit_remove': True,
             'course_remove': 4},
        ]

        subscriptions = Subscription.objects.filter(student__slug='adamcik')
        subscriptions = subscriptions.order_by('id').values_list()
        subscriptions = list(subscriptions)

        for data in post_data:
            original_response = self.client.get(original_url)

            response = self.client.post(url, data)

            self.assertEquals(response.status_code, 302)

            new_subscriptions = list(Subscription.objects.filter(student__slug='adamcik').order_by('id').values_list())
            self.assert_(new_subscriptions != subscriptions)

            subscriptions = new_subscriptions

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

        groups = list(Group.objects.filter(subscription__student__slug='adamcik').order_by('id').values_list())

        for data in post_data:
            original_response = self.client.get(original_url)

            response = self.client.post(url, MultiValueDict(data))

            self.assert_(response['Location'].endswith(original_url))
            self.assertEquals(response.status_code, 302)

            new_groups = list(Group.objects.filter(subscription__student__slug='adamcik').order_by('id').values_list())
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

        lectures = list(Lecture.objects.filter(excluded_from__student__slug='adamcik').order_by('id').values_list())

        for data in post_data:
            original_response = self.client.get(original_url)

            response = self.client.post(url, MultiValueDict(data))

            self.assert_(response['Location'].endswith(original_url))
            self.assertEquals(response.status_code, 302)

            new_lectures = list(Lecture.objects.filter(excluded_from__student__slug='adamcik').order_by('id').values_list())
            self.assert_(lectures != new_lectures)

            lectures = new_lectures

    def test_course_query(self):
        url = reverse('course-query', args=[self.semester.year,
                self.semester.type])

        response = self.client.get(url)

        self.assertEquals("", response.content)

        response = self.client.get(url, {'q': 'COURSE'})
        lines = response.content.split('\n')

        self.assertEquals("COURSE1|Course 1 full name", lines[0])
        self.assertEquals("COURSE2|Course 2 full name", lines[1])
        self.assertEquals("COURSE3|Course 3 full name", lines[2])
        self.assertEquals("COURSE4|Course 4 full name", lines[3])

