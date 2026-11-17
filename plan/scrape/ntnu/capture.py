"""NTNU's acquisition plan, with no operational models or domain parsing.

Course pages discover request identifiers, not saved Plan courses. Schedule
responses also contain rooms, groups, and staff, so those jobs share acquisition.
Syllabus discovery is optional because it contacts the separate Akademika site.
The request dictionaries and source format version also identify offline replay.
"""

import hashlib
import json
from collections.abc import Iterator

import lxml.html
import requests

from plan.scrape import capture, fetch, snapshot

_DEFAULT_JOBS = ("courses", "examinations", "lectures", "rooms")


class Capture:
    source = snapshot.Source(name="ntnu", format_version=1)

    def __init__(self, semester, *, jobs=None, max_per_second=5):
        selected = set(_DEFAULT_JOBS if jobs is None else jobs)
        if not selected or selected - {*_DEFAULT_JOBS, "syllabus"}:
            raise capture.CaptureError(
                "NTNU jobs must be courses, examinations, lectures, rooms, or syllabus"
            )

        self._semester = semester
        self.configuration = {"jobs": sorted(selected)}
        self._jobs = selected
        self._max_per_second = max_per_second

    def run(self, context: capture.Context) -> Iterator[snapshot.CaptureResult]:
        identities = set()
        pages = set()
        for page in range(1, 10001):
            result = context.fetch(
                _course_request(self._semester, page),
                lambda page=page: self._retrieve(_course_request(self._semester, page)),
            )
            yield result

            try:
                if result.status != snapshot.ResultStatus.SUCCESS:
                    raise ValueError("course inventory request failed")

                rows = result.payload.data["courses"]
                if not isinstance(rows, list):
                    raise TypeError("course inventory has no courses array")

                if not rows:
                    break

                fingerprint = hashlib.sha256(
                    json.dumps(rows, sort_keys=True, allow_nan=False).encode()
                ).digest()
                if fingerprint in pages:
                    raise ValueError("course pagination made no progress")

                pages.add(fingerprint)
                if self._jobs & {"lectures", "rooms", "syllabus"}:
                    for row in rows:
                        code, version = row["courseCode"], row["courseVersion"]
                        if (
                            not isinstance(code, str)
                            or not code.strip()
                            or (
                                version is not None
                                and not isinstance(version, (str, int))
                            )
                        ):
                            raise ValueError(
                                "missing source course identifiers for dependent requests"
                            )

                        identities.add(
                            (code, None if version is None else str(version))
                        )
            except (KeyError, TypeError, ValueError) as error:
                yield context.failure({"kind": "discovery", "page": page}, str(error))
                yield context.failure(
                    {
                        "kind": "blocked",
                        "jobs": sorted(self._jobs - {"courses"}),
                        "dependency": "course-inventory",
                    },
                    "course discovery failed; dependent jobs were not run",
                )
                return
        else:
            yield context.failure(
                {"kind": "discovery", "page_limit": 10000},
                "course pagination exceeded its request limit",
            )
            return

        if self._jobs & {"lectures", "rooms"}:
            for code, version in sorted(
                identities, key=lambda value: (value[0], str(value[1]))
            ):
                request = _schedule_request(self._semester, code, version)
                yield context.fetch(
                    request, lambda request=request: self._retrieve(request)
                )

        if "syllabus" in self._jobs:
            for code in sorted({code for code, _ in identities}):
                request = _syllabus_request(code)
                result = context.fetch(
                    request, lambda request=request: self._retrieve(request)
                )
                yield result
                if result.status != snapshot.ResultStatus.SUCCESS:
                    continue

                try:
                    for curriculum_id in _curriculum_ids(result.payload.data):
                        request = _syllabus_request(code, curriculum_id)
                        yield context.fetch(
                            request, lambda request=request: self._retrieve(request)
                        )
                except (TypeError, ValueError, lxml.etree.ParserError) as error:
                    yield context.failure(
                        {"kind": "syllabus-discovery", "course": code},
                        str(error) or type(error).__name__,
                    )

    def _retrieve(self, request) -> snapshot.Payload:
        http = request["http"]
        prepared = fetch.session.prepare_request(
            requests.Request(
                http["method"],
                http["url"],
                params=http.get("params"),
                data=http.get("data"),
            )
        )

        with fetch.rate_limit(self._max_per_second):
            response = fetch.session.send(prepared, timeout=30)

        metadata = {
            "status_code": response.status_code,
            "content_type": response.headers.get("Content-Type", ""),
            "representation": request["representation"],
        }
        error = None if response.ok else f"HTTP {response.status_code}"
        data = response.text

        if request["representation"] == "json":
            try:
                data = response.json()
            except ValueError:
                error = error or "response is not valid JSON"

        return snapshot.Payload(data=data, metadata=metadata, error=error)


def _course_request(semester, page):
    return {
        "kind": "courses",
        "page": page,
        "representation": "json",
        "http": {
            "method": "POST",
            "url": "https://www.ntnu.no/web/studier/emnesok",
            "params": {
                "p_p_id": "courselistportlet_WAR_courselistportlet",
                "p_p_lifecycle": "2",
                "p_p_mode": "view",
                "p_p_resource_id": "fetch-courselist-as-json",
            },
            "data": {
                "english": 0,
                "pageNo": page,
                "semester": semester.year
                if semester.type == "fall"
                else semester.year - 1,
                "sortOrder": "+title",
                "courseAutumn" if semester.type == "fall" else "courseSpring": 1,
            },
        },
    }


def _schedule_request(semester, code, version):
    return {
        "kind": "schedule",
        "course": {"code": code, "version": version},
        "representation": "json",
        "http": {
            "method": "POST",
            "url": "https://www.ntnu.no/web/studier/emner",
            "params": {
                "p_p_id": "coursedetailsportlet_WAR_courselistportlet",
                "p_p_lifecycle": 2,
                "p_p_resource_id": "schedules",
                "_coursedetailsportlet_WAR_courselistportlet_year": semester.year,
                "_coursedetailsportlet_WAR_courselistportlet_courseCode": code,
                "year": semester.year,
                "version": version,
            },
            "data": {},
        },
    }


def _syllabus_request(code, curriculum_id=None):
    return {
        "kind": "syllabus",
        "course": code,
        "curriculum_id": curriculum_id,
        "representation": "text",
        "http": {
            "method": "GET",
            "url": "https://www.akademika.no/curriculum/search",
            "params": {"curriculum": code},
        }
        if curriculum_id is None
        else {
            "method": "GET",
            "url": f"https://www.akademika.no/ajax/curriculum/{curriculum_id}",
        },
    }


def _curriculum_ids(html):
    root = lxml.html.fromstring(html)
    return sorted(
        {
            node.attrib["data-id"]
            for node in root.xpath(
                '//*[contains(concat(" ", normalize-space(@class), " "), " curriculum-search-result ")][@data-id]'
            )
            if node.xpath('.//a[contains(text(),"NTNU")]')
        }
    )
