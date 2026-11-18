"""Interpret archived NTNU source responses without acquiring new data.

Request discovery is replayed against the archive to establish completeness;
missing pages or per-course responses cannot silently authorize deletion.
"""

import json

import lxml.etree
import lxml.html

from plan.common.models import Course
from plan.scrape import records, snapshot, utils
from plan.scrape.ntnu import capture, web


class Decoder:
    def decode(self, archived: snapshot.Snapshot) -> records.SemesterRecords:
        try:
            return self._decode(archived)
        except lxml.etree.LxmlError as error:
            raise ValueError(f"cannot parse archived syllabus HTML: {error}") from error

    def _decode(self, archived: snapshot.Snapshot) -> records.SemesterRecords:
        manifest = archived.manifest
        if manifest.source != capture.Capture.source:
            raise ValueError("unsupported NTNU source format version")

        jobs = manifest.configuration.get("jobs", [])
        if not {"courses", "examinations", "lectures"}.issubset(jobs):
            raise ValueError(
                "NTNU import requires courses, examinations, and lectures jobs"
            )

        def response(request):
            result = archived.result_for(request)
            if result is None or result.status != snapshot.ResultStatus.SUCCESS:
                raise ValueError(
                    f"missing successful archived NTNU request: {request['kind']}"
                )

            return result.payload.data

        semester = manifest.semester
        source_courses = []
        for page in range(1, 10001):
            payload = response(capture._course_request(semester, page))
            rows = payload["courses"]
            if not isinstance(rows, list):
                raise TypeError("course page has no courses array")

            if not rows:
                break

            source_courses.extend(rows)
        else:
            raise ValueError("course inventory has no terminal page")
        normalized_sources = [
            dict(
                row,
                courseVersion=None
                if row["courseVersion"] is None
                else str(row["courseVersion"]),
            )
            for row in source_courses
        ]
        courses = list(_ObservedCourses(semester, normalized_sources).scrape())
        lectures, examinations = [], []

        for course_record in courses:
            reference = {
                "code": course_record["code"],
                "version": course_record["version"],
            }
            course = Course(
                **{
                    key: course_record[key]
                    for key in ("code", "version", "name", "url")
                }
            )
            payload = response(
                capture._schedule_request(semester, course.code, course.version)
            )
            if not isinstance(payload, dict) or not isinstance(
                payload.get("schedules"), list
            ):
                raise TypeError("archived lecture response has no schedules array")

            for row in _ObservedLectures(semester, course, payload).scrape():
                lectures.append(
                    {
                        "course": reference,
                        "type": row["type"],
                        "day": row["day"],
                        "start": row["start"].isoformat(),
                        "end": row["end"].isoformat(),
                        "weeks": sorted(row["weeks"]),
                        "rooms": [list(room) for room in row["rooms"]],
                        "groups": list(row["groups"]),
                        "lecturers": sorted(
                            {
                                staff["name"]
                                for activity in row["_source"]["activities"]
                                for staff in activity["staff"]
                            }
                        ),
                        "title": row["title"] or None,
                        "summary": row["summary"],
                        "stream": row["stream"],
                    }
                )
            dates = set()
            for source in normalized_sources:
                if (source["courseCode"], source["courseVersion"]) != (
                    course.code,
                    course.version,
                ):
                    continue

                for exam in source["exam"]:
                    if exam.get("date") and exam["season"] == (
                        "AUTUMN" if semester.type == "fall" else "SPRING"
                    ):
                        dates.add(utils.parse_date(exam["date"]))
            examinations.extend(
                {"course": reference, "date": date.isoformat()}
                for date in sorted(dates)
            )
            if "syllabus" in jobs:
                syllabus = ""
                for curriculum_id in capture._curriculum_ids(
                    response(capture._syllabus_request(course.code))
                ):
                    root = lxml.html.fromstring(
                        response(capture._syllabus_request(course.code, curriculum_id))
                    )
                    for _, _, href, _ in root.iterlinks():
                        if href.startswith(f"/pensum/{course.code.lower()}-"):
                            syllabus = "https://www.akademika.no" + href
                            break
                    if syllabus:
                        break
                course_record["syllabus"] = syllabus

        return records.SemesterRecords.model_validate_json(
            json.dumps(
                {
                    "semester": semester.model_dump(mode="json"),
                    "courses": courses,
                    "lectures": lectures,
                    "examinations": examinations,
                },
                allow_nan=False,
            )
        )


class _ObservedCourses(web.Courses):
    def __init__(self, semester, source_courses):
        super().__init__(semester)
        self.records = source_courses

    def source_courses(self):
        return self.records


class _ObservedLectures(web.Lectures):
    def __init__(self, semester, course, payload):
        super().__init__(semester)
        self.course = course
        self.payload = payload

    def course_queryset(self):
        return [self.course]

    def fetch_course(self, course):
        return self.payload
