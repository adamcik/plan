from django.contrib import admin
from plan.common.models import *

class CourseAdmin(admin.ModelAdmin):
    list_display = ('name', 'full_name')
    search_fields = ('name', 'full_name')

class UserSetAdmin(admin.ModelAdmin):
    list_display = ('slug', 'course')
    search_fields = ('slug', 'course')
    list_filter = ['slug']

    filter_horizontal = ('groups','exclude')

class LectureAdmin(admin.ModelAdmin):
    list_display = ('course', 'day', 'start_time', 'end_time', 'room', 'type')
    search_fields = ('course__name', 'room__name', 'type__name')
    list_filter = ['day', 'start_time', 'room']
    filter_horizontal = ('weeks', 'groups')
    select_related = True

admin.site.register(UserSet, UserSetAdmin)
admin.site.register(Type)
admin.site.register(Room)
admin.site.register(Group)
admin.site.register(Course, CourseAdmin)
admin.site.register(Lecture, LectureAdmin)
admin.site.register(Lecturer)
admin.site.register(Semester)
