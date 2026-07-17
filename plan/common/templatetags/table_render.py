from django import template

from plan.common.table_render import render_lectures_table, render_schedule_table

register = template.Library()


@register.simple_tag
def native_schedule_table(timetable, rooms, schedule, prev_week, next_week):
    return render_schedule_table(timetable, rooms, schedule, prev_week, next_week)


@register.simple_tag
def native_lectures_table(lectures, groups, rooms, schedule, advanced, tabindex=None):
    return render_lectures_table(lectures, groups, rooms, schedule, advanced, tabindex)
