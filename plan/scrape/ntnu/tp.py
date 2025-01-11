# This file is part of the plan timetable generator, see LICENSE for details.

import json
import re

from plan.common.models import Semester
from plan.scrape import base, fetch, utils

_LOCATIONS = {
    "GLOSHAUGEN": "Trondheim",
    "OLAVSKVART": "Trondheim",
    "ALESUND": "Ålesund",
    "DRAGVOLL": "Trondheim",
    "KALVSKINNE": "Trondheim",
    "OYA": "Trondheim",
    "TUNGA": "Trondheim",
    "GJOVIK": "Gjøvik",
    "TYHOLT": "Trondheim",
    "LERKVALG": "Trondheim",
    "MOHOLT": "Trondheim",
    "TRONDHEIM": "Trondheim",
}


class Courses(base.CourseScraper):
    def scrape(self):
        year = self.semester.year
        if self.semester.type == Semester.SPRING:
            year -= 1

        for c in fetch_courses(self.semester):
            # TODO: Handle mapping to right semester, e.g. AAR4400 has two terms
            # TODO: Handle classes without a campus...
            # TODO: Don't hardcode version?
            # TODO: Filter to active courses for this semester?
            if c["nofterms"] == 1 and c["campusid"] is not None:
                yield {
                    "code": c["id"],
                    "name": c["name"],
                    "version": 1,
                    "url": "https://www.ntnu.no/studier/emner/%s/%s" % (c["id"], year),
                    "locations": [_LOCATIONS[c["campusid"]]],
                }


class Lectures(base.LectureScraper):
    def scrape(self):
        for c in self.course_queryset():
            result = fetch_course_lectures(self.semester, c)

            if "data" not in result or not result["data"]:
                continue

            for methods in result["data"].values():
                for method in methods:
                    for sequence in method["eventsequences"]:
                        current = None

                        for e in sequence["events"]:
                            tmp = {
                                "day": utils.parse_date(e["dtstart"]).weekday(),
                                "start": utils.parse_time(e["dtstart"]),
                                "end": utils.parse_time(e["dtend"]),
                                "rooms": [
                                    (r["id"], r["roomname"], None)
                                    for r in e.get("room", [])
                                ],
                                "groups": process_groups(e.get("studentgroups", [])),
                            }

                            if not current:
                                current = {
                                    "course": c,
                                    "type": method.get(
                                        "teaching-method-name", "teaching-method"
                                    ),
                                    "weeks": [],
                                    "lecturers": [],
                                }
                                current.update(tmp)

                            for key in tmp:
                                if current[key] != tmp[key]:
                                    logging.warning(
                                        "Mismatch %s: %s", self.display(obj), key
                                    )
                                    yield current
                                    current = None
                                    break
                            else:
                                current["weeks"].append(e["weeknr"])

                        if current:
                            yield current


def fetch_courses(semester):
    query = {"sem": convert_semester(semester)}
    resp = fetch.plain("https://tp.uio.no/ntnu/timeplan/emner.php", query)
    return json.loads(re.search(r"var courses = (.+);", resp).group(1))


def fetch_course_lectures(semester, course):
    url = "https://tp.uio.no/ntnu/ws/1.4/"
    query = {"sem": convert_semester(semester), "id": course.code.encode("utf-8")}
    result = fetch.json(url, query=query)

    if not result:
        query["termnr"] = 1
        result = fetch.json(url, query=query)

    return result


def convert_semester(semester):
    if semester.type == Semester.FALL:
        return "%sh" % str(semester.year)[-2:]
    else:
        return "%sv" % str(semester.year)[-2:]


def process_groups(values):
    groups = []
    for value in values:
        match = re.match(r"^([A-ZÆØÅ]+)", value, re.U)
        if match:
            groups.append(match.group(1))
    return groups
