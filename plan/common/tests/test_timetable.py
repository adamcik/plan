# This file is part of the plan timetable generator, see LICENSE for details.

from copy import copy
from dataclasses import replace
from datetime import time

import pytest
from django.utils import translation

from plan.common.models import Lecture, Semester, Student
from plan.common.timetable import Timetable


pytestmark = pytest.mark.django_db


def test_timetable(serialized_schedule_data, cache_isolation, frozen_time):
    # FIXME test expansion
    # FIXME test instert times
    # FIXME test map_to_slot

    # The shared fixture also loads lecture-event coverage not used by this legacy test.
    Lecture.objects.filter(pk=12).delete()

    semester = Semester.objects.get(year=2009, type=Semester.SPRING)
    student = Student.objects.get(slug="adamcik")
    lectures = Lecture.objects.get_lectures_data(semester.id, student.id)

    timetable = Timetable(lectures)
    timetable.place_lectures(week=None)
    timetable.add_markers()

    rows = []
    bottom = {"bottom": True}
    last = {"last": True}
    bottomlast = {"bottom": True, "last": True}

    lectures = {l.lecture_id: l for l in lectures}
    lecture2 = {
        "lecture": lectures[2],
        "rowspan": 2,
        "remove": False,
        "bottom": False,
    }
    lecture3 = {
        "lecture": lectures[3],
        "rowspan": 2,
        "remove": False,
        "bottom": False,
    }
    lecture4 = {
        "lecture": lectures[4],
        "rowspan": 6,
        "remove": False,
        "bottom": False,
    }
    lecture5 = {
        "lecture": lectures[5],
        "rowspan": 2,
        "remove": False,
        "bottom": False,
        "last": True,
    }
    lecture8 = {
        "lecture": lectures[8],
        "rowspan": 1,
        "remove": False,
        "bottom": False,
    }
    lecture9 = {
        "lecture": lectures[9],
        "rowspan": 12,
        "remove": False,
        "bottom": True,
        "last": True,
    }
    lecture10 = {
        "lecture": lectures[10],
        "rowspan": 1,
        "remove": False,
        "bottom": False,
        "last": True,
    }
    lecture11 = {
        "lecture": lectures[11],
        "rowspan": 1,
        "remove": False,
        "bottom": True,
        "last": True,
    }

    rows.append([[lecture2, lecture4, last], [lecture9], [lecture10], [last], [last]])

    lecture2 = copy(lecture2)
    lecture2["remove"] = True
    lecture9 = copy(lecture9)
    lecture9["remove"] = True
    lecture9["bottom"] = False

    lecture4 = copy(lecture4)
    lecture4["remove"] = True

    rows.append([[lecture2, lecture4, lecture5], [lecture9], [last], [last], [last]])

    lecture5 = copy(lecture5)
    lecture5["remove"] = True

    rows.append([[lecture3, lecture4, lecture5], [lecture9], [last], [last], [last]])

    lecture3 = copy(lecture3)
    lecture3["remove"] = True

    rows.append([[lecture3, lecture4, last], [lecture9], [last], [last], [last]])
    rows.append([[{}, lecture4, last], [lecture9], [last], [last], [last]])
    rows.append([[{}, lecture4, last], [lecture9], [last], [last], [last]])
    rows.append([[{}, {}, last], [lecture9], [last], [last], [last]])
    rows.append([[lecture8, {}, last], [lecture9], [last], [last], [last]])
    rows.append([[{}, {}, last], [lecture9], [last], [last], [last]])
    rows.append([[{}, {}, last], [lecture9], [last], [last], [last]])
    rows.append([[{}, {}, last], [lecture9], [last], [last], [last]])
    rows.append(
        [
            [bottom, bottom, bottomlast],
            [lecture9],
            [lecture11],
            [bottomlast],
            [bottomlast],
        ]
    )

    for t, r in zip(timetable.table, rows):
        assert t == r


def test_insert_times_uses_24_hour_format_in_english_locale(
    serialized_schedule_data, cache_isolation, frozen_time
):
    timetable = Timetable([])

    with translation.override("en"):
        timetable.insert_times()

    assert timetable.table[0][0][0]["time"] == "08:15 - 09:00"


def test_timetable_warns_about_unmappable_lectures(
    serialized_schedule_data, cache_isolation, frozen_time, caplog
):
    semester = Semester.objects.get(year=2009, type=Semester.SPRING)
    student = Student.objects.get(slug="adamcik")
    lecture = Lecture.objects.get_lectures_data(semester.id, student.id)[0]
    unmappable = replace(lecture, start=time(23, 45), end=time(23, 59, 59))

    timetable = Timetable([unmappable])

    with caplog.at_level("WARNING", logger="plan.common.timetable"):
        timetable.place_lectures(week=None)

    assert timetable.lectures == []
    assert caplog.messages == [
        f"Skipping lecture {unmappable.lecture_id} outside timetable slots"
    ]
