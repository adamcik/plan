# encoding: utf-8

# Copyright 2008, 2009 Thomas Kongevold Adamcik

# This file is part of Plan.
#
# Plan is free software: you can redistribute it and/or modify
# it under the terms of the Affero GNU General Public License as 
# published by the Free Software Foundation, either version 3 of
# the License, or (at your option) any later version.
#
# Plan is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# Affero GNU General Public License for more details.
#
# You should have received a copy of the Affero GNU General Public
# License along with Plan.  If not, see <http://www.gnu.org/licenses/>.

from plan.common.tests.base import BaseTestCase
from plan.common.models import Lecture, Semester, Deadline, Exam, Course, UserSet

class ManagerTestCase(BaseTestCase):
    fixtures = ['test_data.json', 'test_user.json']

    def test_get_lectures(self):
        # Exclude lectures connected to other courses and excluded from userset
        control = Lecture.objects.exclude(id__in=[6,7])

        # Try showing all lectures
        lectures = Lecture.objects.get_lectures(2009, Semester.SPRING, 'adamcik')
        lectures = filter(lambda l: l.show_week and not l.exclude, lectures)
        self.assertEquals(set(lectures), set(control))

        # Try showing only lectures in week 1
        lectures = Lecture.objects.get_lectures(2009, Semester.SPRING, 'adamcik', 1)
        lectures = filter(lambda l: l.show_week and not l.exclude, lectures)
        self.assertEquals(set(lectures), set(control.filter(week__number=1)))

        # Try showing lectures in week 2
        lectures = Lecture.objects.get_lectures(2009, Semester.SPRING, 'adamcik', 2)
        lectures = filter(lambda l: l.show_week and not l.exclude, lectures)
        self.assertEquals(set(lectures), set(control.filter(week__number=2)))

        # Try lectures in week 3, ie none
        lectures = Lecture.objects.get_lectures(2009, Semester.SPRING, 'adamcik', 3)
        lectures = filter(lambda l: l.show_week and not l.exclude, lectures)
        self.assertEquals(set(lectures), set())

    def test_get_deadlines(self):
        control = Deadline.objects.filter(id__in=[1,2])

        deadlines = Deadline.objects.get_deadlines(2009, Semester.SPRING, 'adamcik')
        self.assertEquals(set(deadlines), set(control))

    def test_get_exams(self):
        exams = Exam.objects.get_exams(2009, Semester.SPRING, 'adamcik')
        self.assertEquals(set(exams), set(Exam.objects.exclude(id__in=[3,4])))

    def test_get_courses(self):
        courses = Course.objects.get_courses(2009, Semester.SPRING, 'adamcik')
        self.assertEquals(set(courses), set(Course.objects.exclude(id=4)))

    def test_get_courses_with_exams(self):
        courses = Course.objects.get_courses_with_exams(2009, Semester.SPRING)
        courses = map(lambda a: a[0], courses)

        # Ensure that courses without exams are included and courses with
        # multiple exams on time per exam
        self.assertEquals(courses, [1, 1, 1, 1, 2, 3, 4, 4])

    def test_get_usersets(self):
        control = UserSet.objects.filter(id__in=[1,2,3])
        usersets = UserSet.objects.get_usersets(2009, Semester.SPRING, 'adamcik')
        self.assertEquals(set(control), set(usersets))

    def test_search(self):
        control = Course.objects.all()
        courses = Course.objects.search(2009, Semester.SPRING, 'COURSE')

        self.assertEquals(set(control), set(courses))

        control = Course.objects.filter(name='COURSE1')
        courses = Course.objects.search(2009, Semester.SPRING, 'COURSE1')

        self.assertEquals(set(control), set(courses))

