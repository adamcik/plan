# This file is part of the plan timetable generator, see LICENSE for details.

import datetime
import logging

from django.conf import settings
from django.utils import formats

from plan.common import utils
from plan.common.models import Lecture

SLOT_END_TIMES = [s[1] for s in settings.TIMETABLE_SLOTS]

logger = logging.getLogger(__name__)


class Timetable:
    slots = len(settings.TIMETABLE_SLOTS)

    def __init__(self, lectures):
        self.lecture_queryset = lectures
        self.lectures = []
        self.table = [[[{}] for a in Lecture.DAYS] for b in range(self.slots)]
        self.span = [1] * len(Lecture.DAYS)
        self.date = [None] * len(Lecture.DAYS)

    def header(self):
        for i, name in Lecture.DAYS:
            yield self.span[i], self.date[i], name

    def set_week(self, year, week):
        first_day = utils.first_date_in_week(year, week)
        self.date = [
            (first_day + datetime.timedelta(days=i)) for i, name in Lecture.DAYS
        ]

    def place_lectures(self, week):
        """Add basics to datastructure"""

        for i, lecture in enumerate(self.lecture_queryset):
            if lecture.exclude or (week and week not in lecture.week_numbers):
                continue

            start, end = self.map_to_slot(lecture)
            if start is None or end is None:
                logger.error("Couldn't map slot for %s, skipping", lecture)
                continue

            rowspan = end - start + 1

            first = start

            # Try to find leftmost row that can fit our lecture, if we run out of
            # rows to test, ie IndexError, we append a fresh one to work with
            try:
                row = 0
                while start <= end:
                    if self.table[start][lecture.day][row]:
                        # One of our time slots is taken, bump the row number and
                        # restart our search
                        row += 1
                        start = first
                    else:
                        start += 1

            except IndexError:
                # We ran out of rows to check, simply append a new row
                for j in range(self.slots):
                    self.table[j][lecture.day].append({})

                # Update the header colspan
                self.span[lecture.day] += 1

            start = first
            remove = False

            while start <= end:
                # Replace the cell we found with a base containing info about our
                # lecture
                self.table[start][lecture.day][row] = {
                    "lecture": lecture,
                    "rowspan": rowspan,
                    "remove": remove,
                    "bottom": start + rowspan == len(self.table),
                }

                # Add lecture to our supplementary data structure and set the
                # remove flag.
                if not remove:
                    remove = True
                    self.lectures.append(
                        {
                            "height": rowspan,
                            "i": start,
                            "j": lecture.day,
                            "k": row,
                            "l": lecture,
                        }
                    )

                start += 1

    def do_expansion(self):
        for lecture in self.lectures:
            # Loop over supplementary data structure using this to figure out which
            # colspan expansions are safe
            i = lecture["i"]
            j = lecture["j"]
            k = lecture["k"]

            height = lecture["height"]

            expand_by = 1

            # Find safe expansion of colspan
            safe = True
            for l in range(k + 1, len(self.table[i][j])):
                for m in range(i, i + height):
                    if self.table[m][j][l]:
                        safe = False
                        break
                if safe:
                    expand_by += 1
                else:
                    break

            self.table[i][j][k]["colspan"] = expand_by
            lecture["width"] = expand_by

            if k + expand_by == len(self.table[i][j]):
                self.table[i][j][k]["last"] = True

            # Remove cells that will get replaced by colspan
            for l in range(k + 1, k + expand_by):
                for m in range(i, i + height):
                    self.table[m][j][l]["remove"] = True

    def add_markers(self):
        for row in self.table:
            for day in row:
                day[-1]["last"] = True
        for day in self.table[-1]:
            for cell in day:
                # only bother with cells that will be shown.
                cell["bottom"] = not cell.get("remove", False)

    def prepare_for_rendering(self):
        """Avoid repeated per-cell template work on large, overlapping schedules."""
        for row in self.table:
            for day in row:
                for cell in day:
                    lecture = cell.get("lecture")
                    cell["css_class"] = ""
                    cell["display_time"] = cell.get("time", "")
                    cell["title"] = ""
                    classes = []
                    if lecture:
                        classes.extend(
                            [
                                "lecture",
                                f"lecture-{lecture.lecture_id}",
                                f"course-{lecture.course_id}",
                            ]
                        )
                    if lecture and lecture.type_optional:
                        classes.append("optional")
                    if cell.get("rowspan") == 1:
                        classes.append("single")
                    for marker in ("last", "bottom", "time"):
                        if cell.get(marker):
                            classes.append(marker)
                    if (
                        lecture
                        or cell.get("time")
                        or cell.get("bottom")
                        or cell.get("last")
                    ):
                        cell["css_class"] = " ".join(classes)
                    if lecture:
                        title = (
                            f"{lecture.course_name} "
                            f"{formats.time_format(lecture.start, 'H:i')}-"
                            f"{formats.time_format(lecture.end, 'H:i')}"
                        )
                        if lecture.title:
                            title += f": {lecture.title}"
                        cell["title"] = title

    def insert_times(self):
        for i, slot in enumerate(settings.TIMETABLE_SLOTS):
            start = formats.time_format(slot[0], "H:i")
            end = formats.time_format(slot[1], "H:i")
            self.table[i].insert(0, [{"time": f"{start} - {end}"}])

    def map_to_slot(self, lecture):
        start, end = None, None

        for i, time in enumerate(SLOT_END_TIMES):
            if start is None and lecture.start < time:
                start = i

            if end is None and lecture.end <= time:
                end = i

        if end is None and lecture.end > time:
            end = i

        return (start, end)
