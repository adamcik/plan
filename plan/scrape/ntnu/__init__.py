# This file is part of the plan timetable generator, see LICENSE for details.

from __future__ import absolute_import
import re

from plan.common.models import Semester

SEMESTER_MAPPING = {Semester.SPRING: 'v',
                    Semester.FALL: 'h'}

CODE_RE = re.compile(r'^[^0-9]+[0-9]+$')
COURSE_RE= re.compile(r'^([^0-9]+[0-9]+)-(\d+)$')


def prefix(semester, template='{letter}{year}'):
    year = str(semester.year)[-2:]
    letter = SEMESTER_MAPPING[semester.type]
    return template.format(letter=letter, year=year)


def valid_course_code(code):
    if not code:
        return False
    return bool(CODE_RE.match(code))


def valid_course_version(version):
    return str(version).isdigit()


def parse_course(raw):
    if not raw:
        return None, None
    m = COURSE_RE.match(raw)
    if m:
        return m.groups()
    return None, None
