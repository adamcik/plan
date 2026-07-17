from django import template
from opentelemetry import trace

from plan.common.table_render import render_lectures_table, render_schedule_table

register = template.Library()
tracer = trace.get_tracer(__name__)


@register.simple_tag
def native_schedule_table(timetable, rooms, schedule, prev_week, next_week):
    with tracer.start_as_current_span("TABLE schedule"):
        return render_schedule_table(timetable, rooms, schedule, prev_week, next_week)


@register.simple_tag
def native_lectures_table(lectures, groups, rooms, schedule, advanced, tabindex=None):
    with tracer.start_as_current_span("TABLE lectures"):
        return render_lectures_table(
            lectures, groups, rooms, schedule, advanced, tabindex
        )
