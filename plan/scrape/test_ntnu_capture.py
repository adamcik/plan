import contextlib
import json
from pathlib import Path
from urllib.parse import parse_qs

import requests

from plan.scrape import capture, fetch, snapshot
from plan.scrape.ntnu import capture as ntnu


def source_course(code="TDT4100"):
    return {
        "courseCode": code,
        "courseVersion": "1",
        "courseName": code,
        "courseUrl": f"https://example.invalid/{code}",
        "location": "Trondheim",
        "exam": [{"date": "2026-05-20", "season": "SPRING"}],
    }


def source_schedule():
    return json.loads(
        (Path(__file__).parent / "ntnu/fixtures/tdt4100_spring_2026.json").read_text()
    )


def install_source(monkeypatch, *, malformed=False, fail_schedule=False):
    calls = []

    def send(request, **kwargs):
        calls.append(request)
        response = requests.Response()
        response.status_code = 200
        response.headers["Content-Type"] = "application/json"
        if "emnesok" in request.url:
            body = parse_qs(request.body)
            data = {"courses": [source_course()] if body["pageNo"] == ["1"] else []}
        else:
            data = (
                {"unparsed": [True, None, {"future": "field"}]}
                if malformed
                else source_schedule()
            )
            if fail_schedule:
                response.status_code = 503
        response._content = json.dumps(data).encode()
        response.encoding = "utf-8"
        return response

    monkeypatch.setattr(fetch.session, "send", send)
    monkeypatch.setattr(fetch, "rate_limit", lambda rate: contextlib.nullcontext())
    return calls


def full_snapshot(monkeypatch, tmp_path):
    install_source(monkeypatch)
    semester = snapshot.Semester(year=2026, type="spring")
    capture.run_capture(ntnu.Capture(semester), semester, tmp_path)
    return capture.load_snapshot(tmp_path)


def test_ntnu_discovers_without_saved_courses_and_preserves_source_json(
    monkeypatch, tmp_path
):
    calls = install_source(monkeypatch)
    semester = snapshot.Semester(year=2026, type="spring")
    capture.run_capture(ntnu.Capture(semester), semester, tmp_path)
    archived = capture.load_snapshot(tmp_path)
    assert len(calls) == 3
    assert archived.results[0].payload.data == {"courses": [source_course()]}
    assert archived.results[1].payload.data == {"courses": []}
    assert archived.results[2].payload.data == source_schedule()


def test_bad_domain_data_is_archived_without_normalization(monkeypatch, tmp_path):
    install_source(monkeypatch, malformed=True)
    semester = snapshot.Semester(year=2026, type="spring")
    capture.run_capture(ntnu.Capture(semester), semester, tmp_path)
    assert capture.load_snapshot(tmp_path).results[2].payload.data == {
        "unparsed": [True, None, {"future": "field"}]
    }


def test_lectures_only_still_discovers_source_courses(monkeypatch, tmp_path):
    calls = install_source(monkeypatch)
    semester = snapshot.Semester(year=2026, type="spring")
    adapter = ntnu.Capture(semester, jobs=["lectures"])
    capture.run_capture(adapter, semester, tmp_path)
    assert len(calls) == 3
    assert capture.load_snapshot(tmp_path).manifest.configuration == {
        "jobs": ["lectures"]
    }


def test_resume_does_not_refetch_inventory_or_other_successes(monkeypatch, tmp_path):
    calls = install_source(monkeypatch, fail_schedule=True)
    semester = snapshot.Semester(year=2026, type="spring")
    adapter = ntnu.Capture(semester)
    assert (
        capture.run_capture(adapter, semester, tmp_path).status
        == snapshot.RunStatus.FAILED
    )
    assert len(calls) == 3
    retried = install_source(monkeypatch)
    assert (
        capture.run_capture(adapter, semester, tmp_path, resume=True).status
        == snapshot.RunStatus.COMPLETE
    )
    assert len(retried) == 1
    assert "emner" in retried[0].url


def test_repeated_course_page_fails_instead_of_looping(monkeypatch, tmp_path):
    calls = install_source(monkeypatch)
    original = fetch.session.send

    def send(request, **kwargs):
        if "emnesok" in request.url:
            request.body = request.body.replace("pageNo=2", "pageNo=1")
        return original(request, **kwargs)

    monkeypatch.setattr(fetch.session, "send", send)
    semester = snapshot.Semester(year=2026, type="spring")
    manifest = capture.run_capture(ntnu.Capture(semester), semester, tmp_path)
    assert manifest.status == snapshot.RunStatus.FAILED
    assert len(calls) == 2
    archived = capture.load_snapshot(tmp_path, require_complete=False)
    assert any(
        "pagination" in (result.payload.error or "") for result in archived.results
    )


def test_optional_syllabus_owns_its_html_discovery(monkeypatch, tmp_path):
    calls = install_source(monkeypatch)
    original = fetch.session.send

    def send(request, **kwargs):
        if "akademika" not in request.url:
            return original(request, **kwargs)
        calls.append(request)
        response = requests.Response()
        response.status_code = 200
        response.encoding = "utf-8"
        response._content = (
            b'<div class="curriculum-search-result" data-id="abc"><a>NTNU</a></div>'
            if "search" in request.url
            else b'<a href="/pensum/tdt4100-example">Books</a>'
        )
        return response

    monkeypatch.setattr(fetch.session, "send", send)
    semester = snapshot.Semester(year=2026, type="spring")
    capture.run_capture(ntnu.Capture(semester, jobs=["syllabus"]), semester, tmp_path)
    archived = capture.load_snapshot(tmp_path)
    assert len(calls) == 4
    assert (
        archived.results[-1].payload.data
        == '<a href="/pensum/tdt4100-example">Books</a>'
    )
    assert archived.results[-1].request["curriculum_id"] == "abc"
