from django import template

from plan.common.table_render import render_schedule_table

register = template.Library()


@register.simple_tag
def native_schedule_table(timetable, rooms, schedule, prev_week, next_week):
    return render_schedule_table(timetable, rooms, schedule, prev_week, next_week)
