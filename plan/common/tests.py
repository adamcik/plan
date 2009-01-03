import datetime

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
    fixtures = ['test_data.json']

    def test_index(self):
        pass

    def test_shortcut(self):
        pass

    def test_schedule(self):
        pass

    def test_advanced_schedule(self):
        pass

class TimetableTestCase(BaseTestCase):
    fixtures = ['test_data.json', 'test_user.json']

    def test_timetable(self):
        from plan.common.models import Lecture, Semester
        from plan.common.timetable import Timetable

        lectures = Lecture.objects.get_lectures(2009, Semester.SPRING, 'adamcik')
        
        timetable = Timetable(lectures)
        timetable.place_lectures()
        timetable.do_expansion()
        timetable.insert_times()

        lectures = dict([(l.id, l) for l in lectures])

        for r in timetable.table:
            print r

        row = [[{'time': '08:15 - 09:00'}], [{}, {}, {}], [{}], [{}], [{}], [{}]]
        row = [[{'time': '09:15 - 10:00'}], [{}, {}, {}], [{}], [{}], [{}], [{}]]
        row = [[{'time': '10:15 - 11:00'}], [{}, {}, {}], [{}], [{}], [{}], [{}]]
        row = [[{'time': '11:15 - 12:00'}], [{}, {}, {}], [{}], [{}], [{}], [{}]]
        row = [[{'time': '12:15 - 13:00'}], [{}, {}, {}], [{}], [{}], [{}], [{}]]
        row = [[{'time': '13:15 - 14:00'}], [{}, {}, {}], [{}], [{}], [{}], [{}]]
        row = [[{'time': '14:15 - 15:00'}], [{}, {}, {}], [{}], [{}], [{}], [{}]]
        row = [[{'time': '15:15 - 16:00'}], [{}, {}, {}], [{}], [{}], [{}], [{}]]
        row = [[{'time': '16:15 - 17:00'}], [{}, {}, {}], [{}], [{}], [{}], [{}]]
        row = [[{'time': '17:15 - 18:00'}], [{}, {}, {}], [{}], [{}], [{}], [{}]]
        row = [[{'time': '18:15 - 19:00'}], [{}, {}, {}], [{}], [{}], [{}], [{}]]
        row = [[{'time': '19:15 - 20:00'}], [{}, {}, {}], [{}], [{}], [{}], [{}]]

class ManagerTestCase(BaseTestCase):
    fixtures = ['test_data.json', 'test_user.json']

    def test_get_lectures(self):
        from plan.common.models import Lecture, Semester

        control = Lecture.objects.exclude(id__in=[6,7])
        
        lectures = Lecture.objects.get_lectures(2009, Semester.SPRING, 'adamcik')
        lectures = filter(lambda a: a.show_week and not a.exclude, lectures)
        self.assertEquals(set(lectures), set(control))

        lectures = Lecture.objects.get_lectures(2009, Semester.SPRING, 'adamcik', 1)
        lectures = filter(lambda a: a.show_week and not a.exclude, lectures)
        self.assertEquals(set(lectures), set(control.filter(weeks__number=1)))

        lectures = Lecture.objects.get_lectures(2009, Semester.SPRING, 'adamcik', 2)
        lectures = filter(lambda a: a.show_week and not a.exclude, lectures)
        self.assertEquals(set(lectures), set(control.filter(weeks__number=2)))

        lectures = Lecture.objects.get_lectures(2009, Semester.SPRING, 'adamcik', 3)
        lectures = filter(lambda a: a.show_week and not a.exclude, lectures)
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
