# Copyright 2008, 2009 Thomas Kongevold Adamcik
# 2009 IME Faculty Norwegian University of Science and Technology

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

from django.contrib import admin
from django.contrib.auth.models import User

from plan.common.models import Course, Exam, Group, Lecture, Lecturer, \
        Room, Semester, LectureType, Deadline, UserSet, Student

class CourseAdmin(admin.ModelAdmin):
    list_display = ('code', 'points', 'name', 'url', 'semester')
    list_filter = ('semester',)
    search_fields = ('code', 'name')

class ExamAdmin(admin.ModelAdmin):
    list_display = ('course', 'exam_date', 'exam_time', 'duration')
    search_fields = ('course__code',)
    list_filter = ['duration']

class LectureAdmin(admin.ModelAdmin):
    list_display = ('course', 'day', 'start', 'end', 'type')

    search_fields = ('course__code', 'type__name')

    filter_horizontal = ('groups', 'lecturers', 'rooms')

    list_per_page = 50
    list_filter = ['day', 'start', 'end', 'rooms']
    list_select_related = True

class UserSetAdmin(admin.ModelAdmin):
    list_display = ('student', 'course')
    search_fields = ('student__slug', 'course__code')

class StudentAdmin(admin.ModelAdmin):
    ordering = ('slug',)

class LectureTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'optional')

class DeadlineAdmin(admin.ModelAdmin):
    ordering = ('userset__slug', 'userset__course__code', 'date', 'time')

    search_fields = ('userset__slug', 'userset__course__code', 'task')

    list_display = ('course', 'slug', 'date', 'time', 'task')
    list_display_links = ('course', 'slug')

admin.site.register(User)
admin.site.register(Course, CourseAdmin)
admin.site.register(Exam, ExamAdmin)
admin.site.register(Group)
admin.site.register(Lecture, LectureAdmin)
admin.site.register(Lecturer)
admin.site.register(Room)
admin.site.register(Semester)
admin.site.register(LectureType, LectureTypeAdmin)
admin.site.register(Deadline, DeadlineAdmin)
admin.site.register(Student, StudentAdmin)
admin.site.register(UserSet, UserSetAdmin)
