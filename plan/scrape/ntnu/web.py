# This file is part of the plan timetable generator, see LICENSE for details.

import datetime
import logging
import re
from urllib.parse import quote_plus

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

        for c in tqdm.tqdm(self.course_queryset(), unit="courses"):
            course = fetch_course_lectures(self.semester, c)
            groupings = {}
            for activity in course.get("schedules", []):
                if activity["artermin"] != ntnu_semeter:
                    continue

                start = datetime.datetime.fromtimestamp(activity["from"] / 1000)
                end = datetime.datetime.fromtimestamp(activity["to"] / 1000)
                lecture_type = activity.get("name", activity["acronym"]).strip()
                title = re.sub(r"^\d+(-\d*)?\s?", "", activity["title"]).strip()
                summary = activity["summary"].strip()
                stream = None

                groups = set(activity.get("studyProgramKeys", []))
                # TODO: Treat this a group?
                # disiplin = set(activity.get("disiplin", []))

                # TODO: migrate `mlreal` to `MLREAL`
                # TODO: match existing code without looking at case

                # Remove these if the are equal course code or type
                if not title or title == c.code or lecture_type == title:
                    title = None
                if (
                    not summary
                    or summary == c.code
                    or summary == lecture_type
                    or summary == title
                ):
                    summary = None

                rooms = set()
                for r in activity["rooms"]:
                    room_code = r["id"]
                    room_name = r["room"]
                    room_url = r.get("url", "")

                    if r["building"] == "Digital undervisning":
                        # Try to store stream links on the lectures:
                        assert stream is None
                        stream = room_url
                        continue
                    elif not room_url:
                        # Fallback to searching if not known:
                        room_url = (
                            "https://use.mazemap.com/#v=1&config=ntnu&search=%s"
                            % quote_plus(room_name)
                        )

                    rooms.add((room_code, room_name, room_url))

                staff = {(s["name"], s.get("url", "")) for s in activity["staff"]}

                key = (
                    start.weekday(),
                    start.time(),
                    end.time(),
                    lecture_type,
                    title or "",
                    summary or "",
                    stream or "",
                    tuple(sorted(groups)),
                    tuple(sorted(rooms)),
                    tuple(sorted(staff)),
                    # tuple(sorted(disiplin)),
                )
                groupings.setdefault(key, set()).add(activity["week"])

            # TODO: see if we can move the grouping to the base scraper?
            for key, weeks in sorted(groupings.items()):
                (
                    day,
                    start,
                    end,
                    lecture_type,
                    title,
                    summary,
                    stream,
                    groups,
                    rooms,
                    lecturers,
                    # disiplin,
                ) = key

                yield {
                    "course": c,
                    "type": lecture_type,
                    "day": day,
                    "start": start,
                    "end": end,
                    "weeks": weeks,
                    "rooms": rooms,
                    "groups": groups,
                    # FIXME: Why is staff dropped?
                    "lecturers": tuple(),
                    # TODO: Pass through displin to use as groups for med students?
                    # "disiplin": disiplin,
                    "title": title,
                    "summary": summary or None,
                    "stream": stream or None,
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
