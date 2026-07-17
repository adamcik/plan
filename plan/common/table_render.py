"""Minimal native HTML rendering for timetable performance experiments."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from html import escape
from typing import NewType

from django.urls import reverse
from django.utils import formats, translation
from django.utils.safestring import SafeString, mark_safe


_SafeHtml = NewType("_SafeHtml", str)


def _escape(value: object) -> _SafeHtml:
    """Escape dynamic content for insertion into HTML text or attributes."""
    return _SafeHtml(escape(str(value), quote=True))


# `_` keeps repeated table markup compact within this private renderer.
def _(
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


def _join(parts: Iterable[_SafeHtml]) -> _SafeHtml:
    """Concatenate HTML-safe fragments."""
    return _SafeHtml("".join(parts))


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
            _(
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
            _(
                "a",
                _SafeHtml("&raquo;"),
                attributes={"id": "next", "class": "noprint", "href": url},
            )
        )

    header_cells = [_("th", attributes={"class": "time"})]
    for span, date, day in timetable.header():
        content = _("span", _escape(day), attributes={"class": "day"})
        if date:
            content = _join(
                [
                    content,
                    _(
                        "span",
                        _escape(formats.date_format(date, "j M.")),
                        attributes={"class": "date"},
                    ),
                ]
            )
        header_cells.append(
            _("th", content, attributes={"colspan": span if span else None})
        )

    body_rows = []
    for row_number, timetable_row in enumerate(timetable.table):
        cells = []
        for cell_group in timetable_row:
            if not cell_group:
                cells.append(
                    _(
                        "td",
                        _("div", attributes={"class": "wrapper"}),
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
                        f"{formats.time_format(lecture.start, 'H:i')}-"
                        f"{formats.time_format(lecture.end, 'H:i')}"
                    )
                    if lecture.title:
                        title += f": {lecture.title}"
                    attributes["title"] = title
                    content = _join(
                        [
                            content,
                            _(
                                "div",
                                _escape(lecture.alias or lecture.course_code),
                                attributes={"class": "course"},
                            ),
                        ]
                    )
                    room_links: list[_SafeHtml] = []
                    if lecture.stream:
                        room_links.append(
                            _(
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
                                _(
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
                            _(
                                "div",
                                _join(room_links),
                                attributes={"class": "room"},
                            ),
                        ]
                    )
                    content = _join(
                        [
                            content,
                            _(
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
                    _(
                        "td",
                        _("div", content, attributes={"class": "wrapper"}),
                        attributes=attributes,
                    )
                )
        body_rows.append(
            _(
                "tr",
                _join(cells),
                attributes={
                    "class": f"{'odd' if row_number % 2 == 0 else 'even'}"
                    f"{' first' if row_number == 0 else ''}"
                },
            )
        )

    output.append(
        _(
            "div",
            _(
                "table",
                _join(
                    [
                        _("thead", _("tr", _join(header_cells))),
                        _("tbody", _join(body_rows)),
                    ]
                ),
                attributes={"id": "schedule"},
            ),
            attributes={"class": "overflow"},
        )
    )
    return mark_safe(_join(output))
