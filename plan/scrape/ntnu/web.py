# This file is part of the plan timetable generator, see LICENSE for details.

import datetime
import logging
import re

import tqdm

from plan.common.models import Course, Semester
from plan.scrape import base, fetch, utils

# TODO(adamcik): link to http://www.ntnu.no/eksamen/sted/?dag=120809 for exams?


class Courses(base.CourseScraper):
    def scrape(self):
        for course in fetch_courses(self.semester):
            code = course["courseCode"]
            version = course["courseVersion"]
            location = course["location"].split(",")

            yield {
                "code": code,
                "name": course["courseName"],
                "version": version,
                "url": course["courseUrl"],
                "locations": location,
            }


class Exams(base.ExamScraper):
    def scrape(self):
        for course in fetch_courses(self.semester):
            try:
                obj = Course.objects.get(
                    code=course["courseCode"],
                    version=course["courseVersion"],
                    semester=self.semester,
                )
            except Course.DoesNotExist:
                continue

            seen = set()
            for exam in course["exam"]:
                if not exam.get("date"):
                    continue
                elif self.semester.type == Semester.FALL and exam["season"] != "AUTUMN":
                    continue
                elif (
                    self.semester.type == Semester.SPRING and exam["season"] != "SPRING"
                ):
                    continue

                date = utils.parse_date(exam["date"])
                if date in seen:
                    continue

                seen.add(date)
                yield {
                    "course": obj,
                    "exam_date": date,
                }


class Lectures(base.LectureScraper):
    def scrape(self):
        if self.semester.type == Semester.FALL:
            ntnu_semeter = "%d_HØST" % self.semester.year
        else:
            ntnu_semeter = "%d_VÅR" % self.semester.year

        for c in tqdm.tqdm(self.course_queryset(), unit='courses'):
            course = fetch_course_lectures(self.semester, c)
            groupings = {}
            for activity in course.get("schedules", []):
                if activity["artermin"] != ntnu_semeter:
                    continue

                start = datetime.datetime.fromtimestamp(activity["from"] / 1000)
                end = datetime.datetime.fromtimestamp(activity["to"] / 1000)
                name = activity.get("name", activity["acronym"]).strip()
                title = re.sub(r"^\d+(-\d*)?\s?", "", activity["title"]).strip()
                groups = set(activity.get("studyProgramKeys", []))

                if not title or title == c.code:  # or name == title:
                    title = None

                # FIXME: This heuristic is broken, but I need a migration plan
                if title is not None:
                    if not groups and title:
                        groups.add(title)
                        title = None
                    elif name in ("Seminar", "Gruppe") and title != name:
                        groups.add(title)
                        title = None

                if (
                    not title
                    and activity["summary"].strip() != activity["title"].strip()
                ):
                    title = activity["summary"].strip()

                # TODO: handle building='Digital undervisning' such that we get
                # unique url per room.  Current model assumes unique code per
                # room, which we need to work around or change.

                rooms = set()
                for r in activity["rooms"]:
                    room_code = r["id"]
                    room_name = r["room"]
                    room_url = r.get("url", "")

                    # TODO: Move storing the stream link to the lecture itself?

                    # HACK: This keeps the URL stable for virtual lectures,
                    # ideally we would have a virtual room per lecture so we
                    # can use the link with access code etc.
                    if room_code == "194_VR_OM":
                        room_url = "https://ntnu.zoom.us/"

                    rooms.add((room_code, room_name, room_url))

                staff = {(s["name"], s.get("url", "")) for s in activity["staff"]}

                key = (
                    start.weekday(),
                    start.time(),
                    end.time(),
                    name,
                    title or "",
                    tuple(sorted(groups)),
                    tuple(sorted(rooms)),
                    tuple(sorted(staff)),
                )
                groupings.setdefault(key, set()).add(activity["week"])

            # TODO: see if we can move the grouping to the base scraper?
            for key, weeks in sorted(groupings.items()):
                day, start, end, name, title, groups, rooms, lecturers = key
                yield {
                    "course": c,
                    "type": name,
                    "day": day,
                    "start": start,
                    "end": end,
                    "weeks": weeks,
                    "rooms": rooms,
                    "groups": groups,
                    "lecturers": tuple(),
                    "title": title,
                }


class Rooms(base.RoomScraper):
    def scrape(self):
        seen = set()
        # TODO: this is broken after switch from timetable to schedules
        for c in Course.objects.filter(semester=self.semester):
            course = fetch_course_lectures(self.semester, c)
            for activity in course.get("summarized", []):
                for room in activity.get("rooms", []):
                    if room["syllabusKey"] not in seen:
                        seen.add(room["syllabusKey"])
                        yield {
                            "code": room["syllabusKey"],
                            "name": room["romNavn"],
                            "url": room.get("url"),
                        }


def fetch_course_lectures(semester, course):
    url = "https://www.ntnu.no/web/studier/emner"
    query = {
        "p_p_id": "coursedetailsportlet_WAR_courselistportlet",
        "p_p_lifecycle": 2,
        "p_p_resource_id": "schedules",
        "_coursedetailsportlet_WAR_courselistportlet_year": semester.year,
        "_coursedetailsportlet_WAR_courselistportlet_courseCode": course.code.encode(
            "utf-8"
        ),
        "year": semester.year,
        "version": course.version,
    }
    return fetch.json(url, query=query, data={})


def fetch_courses(semester):
    """
    https://www.ntnu.no/web/studier/emnesok?
        p_p_id=courselistportlet_WAR_courselistportlet
        p_p_lifecycle=2
        p_p_state=normal
        p_p_mode=view
        p_p_resource_id=fetch-courselist-as-json
        p_p_cacheability=cacheLevelPage
        p_p_col_id=column-1
        p_p_col_pos=1
        p_p_col_count=2

    X-Requested-With: XMLHttpRequest
    Cookie: GUEST_LANGUAGE_ID=nb_NO

    Data:
        semester=2018
        gjovik=0
        trondheim=1
        alesund=0
        faculty=-1
        institute=-1
        multimedia=0
        english=0
        phd=0
        courseAutumn=0
        courseSpring=1
        courseSummer=0
        searchQueryString=
        pageNo=1
        season=spring
        sortOrder=%2Btitle
        year=
    """

    if semester.type == Semester.FALL:
        year = semester.year
    else:
        year = semester.year - 1

    url = "https://www.ntnu.no/web/studier/emnesok"

    query = {
        "p_p_id": "courselistportlet_WAR_courselistportlet",
        "p_p_lifecycle": "2",
        "p_p_mode": "view",
        "p_p_resource_id": "fetch-courselist-as-json",
    }

    data = {
        "english": 0,
        "pageNo": 1,
        "semester": year,
        "sortOrder": "+title",
    }

    if semester.type == Semester.FALL:
        data["courseAutumn"] = 1
    else:
        data["courseSpring"] = 1

    seen = set()

    while True:
        result = fetch.json(url, query=query, data=data, verbose=True)
        # TODO use hasMoreResults?
        data["pageNo"] += 1

        if not result["courses"]:
            break

        for course in result["courses"]:
            key = (course["courseCode"], course["courseVersion"])
            key += tuple(course["location"].split(","))

            if key in seen:
                logging.warn("Skipping duplicate %r", key)
            else:
                seen.add(key)
                yield course
