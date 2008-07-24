from django.contrib import admin
from plan.common.models import *

class CourseAdmin(admin.ModelAdmin):
    list_display = ('name', 'full_name')
    search_fields = ('name', 'full_name')

class UserSetAdmin(admin.ModelAdmin):
    list_display = ('slug', 'course')
    search_fields = ('slug', 'course')
    list_filter = ['slug']

class LectureAdmin(admin.ModelAdmin):
    list_display = ('course', 'day', 'start_time', 'end_time', 'room')
    search_fields = list_display
    list_filter = ['day', 'start_time', 'room']

admin.site.register(UserSet, UserSetAdmin)
admin.site.register(Type)
admin.site.register(Room)
admin.site.register(Group)
admin.site.register(Course, CourseAdmin)
admin.site.register(Lecture, LectureAdmin)
admin.site.register(Semester)
