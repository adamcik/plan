"""Minimal native HTML rendering for timetable performance experiments."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from html import escape
from typing import NewType

from django.urls import reverse
from django.templatetags.static import static
from django.utils import dates, formats, translation
from django.utils.safestring import SafeString, mark_safe

from plan.common.utils import compact_sequence


_SafeHtml = NewType("_SafeHtml", str)


def _escape(value: object) -> _SafeHtml:
    """Escape dynamic content for insertion into HTML text or attributes."""
    return _SafeHtml(escape(str(value), quote=True))


def _el(
    tag: str,
    content: _SafeHtml = _SafeHtml(""),
    *,
    attributes: Mapping[str, object] | None = None,
) -> _SafeHtml:
    """Build renderer-controlled markup and escape dynamic attribute values.

    Tags and attribute names must be literals selected by the renderer. Content
    is already safe HTML; values in ``attributes`` are escaped here.
    """
    rendered_attributes = ""
    if attributes:
        rendered_attributes = "".join(
            f' {name}="{_escape(value)}"'
            for name, value in attributes.items()
            if value is not None and value is not False
        )
    return _SafeHtml(f"<{tag}{rendered_attributes}>{content}</{tag}>")


def _void(tag: str, *, attributes: Mapping[str, object] | None = None) -> _SafeHtml:
    """Build a renderer-controlled void element."""
    rendered_attributes = ""
    if attributes:
        rendered_attributes = "".join(
            f' {name}="{_escape(value)}"'
            for name, value in attributes.items()
            if value is not None and value is not False
        )
    return _SafeHtml(f"<{tag}{rendered_attributes} />")


def _join(parts: Iterable[_SafeHtml]) -> _SafeHtml:
    """Concatenate HTML-safe fragments."""
    return _SafeHtml("".join(parts))


def _time(value) -> str:
    """Render the fixed ``H:i`` format used by the template oracles."""
    return f"{value.hour:02d}:{value.minute:02d}"


def render_schedule_table(
    timetable, rooms, schedule, prev_week, next_week
) -> SafeString:
    """Render the current schedule-table template without template-node overhead."""
    output: list[_SafeHtml] = []
    if prev_week:
        url = reverse(
            "schedule-week", args=[schedule.semester, schedule.student.slug, prev_week]
        )
        output.append(
            _el(
                "a",
                _SafeHtml("&laquo;"),
                attributes={"id": "previous", "class": "noprint", "href": url},
            )
        )
    if next_week:
        url = reverse(
            "schedule-week", args=[schedule.semester, schedule.student.slug, next_week]
        )
        output.append(
            _el(
                "a",
                _SafeHtml("&raquo;"),
                attributes={"id": "next", "class": "noprint", "href": url},
            )
        )

    header_cells = [_el("th", attributes={"class": "time"})]
    for span, date, day in timetable.header():
        content = _el("span", _escape(day), attributes={"class": "day"})
        if date:
            content = _join(
                [
                    content,
                    _el(
                        "span",
                        _escape(formats.date_format(date, "j M.")),
                        attributes={"class": "date"},
                    ),
                ]
            )
        header_cells.append(
            _el("th", content, attributes={"colspan": span if span else None})
        )

    body_rows = []
    for row_number, timetable_row in enumerate(timetable.table):
        cells = []
        for cell_group in timetable_row:
            if not cell_group:
                cells.append(
                    _el(
                        "td",
                        _el("div", attributes={"class": "wrapper"}),
                    )
                )
                continue
            for timetable_cell in cell_group:
                if timetable_cell.get("remove"):
                    continue
                lecture = timetable_cell.get("lecture")
                classes = []
                if lecture:
                    classes.extend(
                        [
                            "lecture",
                            f"lecture-{lecture.lecture_id}",
                            f"course-{lecture.course_id}",
                        ]
                    )
                    if lecture.type_optional:
                        classes.append("optional")
                if timetable_cell.get("rowspan") == 1:
                    classes.append("single")
                if timetable_cell.get("last"):
                    classes.append("last")
                if timetable_cell.get("bottom"):
                    classes.append("bottom")
                if timetable_cell.get("time"):
                    classes.append("time")

                attributes: dict[str, object] = {
                    "colspan": timetable_cell.get("colspan")
                    if timetable_cell.get("colspan", 1) > 1
                    else None,
                    "rowspan": timetable_cell.get("rowspan")
                    if timetable_cell.get("rowspan", 1) > 1
                    else None,
                    "class": " ".join(classes) if classes else None,
                }
                content = _SafeHtml("")
                if lecture:
                    title = (
                        f"{lecture.course_name} "
                        f"{_time(lecture.start)}-{_time(lecture.end)}"
                    )
                    if lecture.title:
                        title += f": {lecture.title}"
                    attributes["title"] = title
                    content = _join(
                        [
                            content,
                            _el(
                                "div",
                                _escape(lecture.alias or lecture.course_code),
                                attributes={"class": "course"},
                            ),
                        ]
                    )
                    room_links: list[_SafeHtml] = []
                    if lecture.stream:
                        room_links.append(
                            _el(
                                "a",
                                _escape(translation.gettext("Stream")),
                                attributes={"href": lecture.stream},
                            )
                        )
                    lecture_rooms = rooms.get(lecture.lecture_id, ())[:2]
                    if lecture.stream and lecture_rooms:
                        room_links.append(_SafeHtml(","))
                    for index, room_data in enumerate(lecture_rooms):
                        room_name = room_data["name"]
                        room_url = room_data["url"]
                        if room_url:
                            room_links.append(
                                _el(
                                    "a",
                                    _escape(room_name),
                                    attributes={"href": room_url},
                                )
                            )
                        else:
                            room_links.append(_escape(room_name))
                        if index + 1 < len(lecture_rooms):
                            room_links.append(_SafeHtml(","))
                    content = _join(
                        [
                            content,
                            _el(
                                "div",
                                _join(room_links),
                                attributes={"class": "room"},
                            ),
                        ]
                    )
                    content = _join(
                        [
                            content,
                            _el(
                                "div",
                                _escape(lecture.title or lecture.type_name or ""),
                                attributes={"class": "type"},
                            ),
                        ]
                    )
                if timetable_cell.get("time"):
                    content = _join(
                        [
                            content,
                            _SafeHtml(
                                _escape(timetable_cell["time"]).replace(" ", "&nbsp;")
                            ),
                        ]
                    )
                cells.append(
                    _el(
                        "td",
                        _el("div", content, attributes={"class": "wrapper"}),
                        attributes=attributes,
                    )
                )
        body_rows.append(
            _el(
                "tr",
                _join(cells),
                attributes={
                    "class": f"{'odd' if row_number % 2 == 0 else 'even'}"
                    f"{' first' if row_number == 0 else ''}"
                },
            )
        )

    output.append(
        _el(
            "div",
            _el(
                "table",
                _join(
                    [
                        _el("thead", _el("tr", _join(header_cells))),
                        _el("tbody", _join(body_rows)),
                    ]
                ),
                attributes={"id": "schedule"},
            ),
            attributes={"class": "overflow"},
        )
    )
    return mark_safe(_join(output))


def render_lectures_table(
    lectures, groups, rooms, schedule, advanced: bool, tabindex: int | None = None
) -> SafeString:
    """Render the lecture-list include without template-node overhead."""
    if not lectures:
        return mark_safe("")

    base_tabindex = tabindex or 0
    output: list[_SafeHtml] = [_el("h2", _escape(translation.gettext("Lecture list")))]
    form_url = reverse(
        "change-lectures", args=[schedule.semester, schedule.student.slug]
    )
    form_content: list[_SafeHtml] = []
    if advanced:
        controls = _el(
            "p",
            _join(
                [
                    _escape(translation.gettext("Filter") + ":"),
                    _SafeHtml(" "),
                    _void(
                        "input",
                        attributes={
                            "data-filter": "true",
                            "placeholder": "...",
                            "tabindex": base_tabindex + 3,
                        },
                    ),
                    _SafeHtml(" "),
                    _escape(translation.gettext("Select") + ":"),
                    _SafeHtml(" "),
                    _el(
                        "button",
                        _escape(translation.gettext("All")),
                        attributes={
                            "data-toggle": "true",
                            "tabindex": base_tabindex + 1,
                        },
                    ),
                    _SafeHtml(" "),
                    _el(
                        "button",
                        _escape(translation.gettext("None")),
                        attributes={
                            "data-toggle": "false",
                            "tabindex": base_tabindex + 2,
                        },
                    ),
                ]
            ),
        )
        submit = _el(
            "p",
            _el(
                "button",
                _join(
                    [
                        _SafeHtml(
                            f'<svg class="icon" aria-hidden="true"><use href="{static("icons.svg")}#hide"></use></svg> '
                        ),
                        _escape(translation.gettext("Hide selected lectures")),
                    ]
                ),
                attributes={
                    "type": "submit",
                    "class": "right",
                    "tabindex": base_tabindex + 5,
                },
            ),
            attributes={"class": "right"},
        )
        form_content.append(
            _el(
                "div",
                _join(
                    [
                        _el("div", controls, attributes={"class": "yui-u first"}),
                        _el("div", submit, attributes={"class": "yui-u"}),
                    ]
                ),
                attributes={"class": "yui-g noprint"},
            )
        )
    else:
        advanced_url = reverse(
            "schedule-advanced", args=[schedule.semester, schedule.student.slug]
        )
        message = translation.gettext(
            '\n          Go to <a href="%(advanced_url)s#lectures">advanced options</a>\n'
            "          to toggle which lectures to hide.\n        "
        ) % {"advanced_url": _escape(advanced_url)}
        form_content.append(_el("p", _SafeHtml(message)))

    headers: list[_SafeHtml] = []
    if advanced:
        headers.append(_el("th"))
    for label, search in (
        ("Course", "course"),
        ("Day", "day"),
        ("Time", "time"),
        ("Info", "info"),
        ("Rooms", "rooms"),
        ("Type", "type"),
        ("Groups", "groups"),
        ("Weeks", None),
    ):
        headers.append(
            _el(
                "th",
                _escape(translation.gettext(label)),
                attributes={"data-search": search},
            )
        )

    rows: list[_SafeHtml] = []
    for lecture in lectures:
        cells: list[_SafeHtml] = []
        if advanced:
            exclude_title = translation.gettext("Hide %(l)s") % {"l": lecture}
            cells.append(
                _el(
                    "td",
                    _void(
                        "input",
                        attributes={
                            "type": "checkbox",
                            "name": "exclude",
                            "value": lecture.lecture_id,
                            "checked": "checked" if lecture.exclude else None,
                            "class": "noprint",
                            "title": exclude_title,
                            "tabindex": base_tabindex + 4,
                        },
                    ),
                )
            )
        try:
            day = dates.WEEKDAYS[int(lecture.day)]
        except (TypeError, ValueError, KeyError):
            day = ""
        room_content: list[_SafeHtml] = []
        lecture_rooms = rooms.get(lecture.lecture_id, ())
        if lecture.stream:
            room_content.append(
                _el(
                    "a",
                    _escape(translation.gettext("Stream")),
                    attributes={
                        "href": reverse("redirect_stream", args=[lecture.lecture_id])
                    },
                )
            )
            if lecture_rooms:
                room_content.append(_SafeHtml(","))
        for index, room in enumerate(lecture_rooms):
            if room["url"]:
                room_content.append(
                    _el(
                        "a",
                        _escape(room["name"]),
                        attributes={
                            "href": reverse("redirect_room", args=[room["id"]])
                        },
                    )
                )
            else:
                room_content.append(_escape(room["name"]))
            if index + 1 < len(lecture_rooms):
                room_content.append(_SafeHtml(","))
        if not lecture_rooms:
            room_content.append(_SafeHtml("&nbsp;"))
        cells.extend(
            [
                _el("td", _escape(lecture.alias or lecture.course_code)),
                _el("td", _escape(day)),
                _el(
                    "td",
                    _SafeHtml(f"{_time(lecture.start)}-{_time(lecture.end)}"),
                    attributes={"class": "nowrap"},
                ),
                _el(
                    "td",
                    _join(
                        [
                            _escape(lecture.title or ""),
                            _SafeHtml(" - ")
                            if lecture.title and lecture.summary
                            else _SafeHtml(""),
                            _escape(lecture.summary or ""),
                        ]
                    ),
                    attributes={"class": "small"},
                ),
                _el("td", _join(room_content), attributes={"class": "small"}),
                _el(
                    "td",
                    _escape(lecture.type_name or ""),
                    attributes={"class": "small"},
                ),
                _el(
                    "td",
                    _escape(
                        ", ".join(
                            str(group) for group in groups.get(lecture.lecture_id, ())
                        )
                    ),
                    attributes={"class": "small"},
                ),
                _el(
                    "td",
                    _escape(", ".join(compact_sequence(lecture.week_numbers))),
                    attributes={"class": "small nowrap"},
                ),
            ]
        )
        rows.append(
            _el(
                "tr",
                _join(cells),
                attributes={
                    "class": (
                        f"course-{lecture.course_id} lecture-{lecture.lecture_id}"
                        f"{' excluded' if lecture.exclude else ''}"
                    ),
                    "title": lecture.course_name,
                },
            )
        )
    form_content.append(
        _el(
            "div",
            _el(
                "table",
                _join(
                    [
                        _el("thead", _el("tr", _join(headers))),
                        _el("tbody", _join(rows)),
                    ]
                ),
                attributes={"id": "lectures"},
            ),
            attributes={"class": "overflow"},
        )
    )
    output.append(
        _el(
            "form",
            _join(form_content),
            attributes={
                "action": form_url,
                "method": "post",
                "data-toggle-container": "true",
            },
        )
    )
    return mark_safe(_join(output))
