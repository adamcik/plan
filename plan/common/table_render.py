"""Minimal native HTML rendering for timetable performance experiments."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from html import escape

from django.urls import reverse
from django.utils import formats, translation
from django.utils.safestring import SafeString, mark_safe


def _escaped(value: object) -> str:
    return escape(str(value), quote=True)


def _attributes(attributes: Mapping[str, object] | None) -> str:
    if not attributes:
        return ""
    return "".join(
        f' {name}="{_escaped(value)}"'
        for name, value in attributes.items()
        if value is not None and value is not False
    )


def cell(
    tag: str, content: str, *, attributes: Mapping[str, object] | None = None
) -> str:
    return f"<{tag}{_attributes(attributes)}>{content}</{tag}>"


def row(cells: Iterable[str], *, attributes: Mapping[str, object] | None = None) -> str:
    return f"<tr{_attributes(attributes)}>{''.join(cells)}</tr>"


def section(tag: str, rows: Iterable[str]) -> str:
    return f"<{tag}>{''.join(rows)}</{tag}>"


def table(
    parts: Iterable[str], *, attributes: Mapping[str, object] | None = None
) -> str:
    return f"<table{_attributes(attributes)}>{''.join(parts)}</table>"


def render_schedule_table(
    timetable, rooms, schedule, prev_week, next_week
) -> SafeString:
    """Render the current schedule-table template without template-node overhead."""
    output: list[str] = []
    if prev_week:
        url = reverse(
            "schedule-week", args=[schedule.semester, schedule.student.slug, prev_week]
        )
        output.append(
            cell(
                "a",
                "&laquo;",
                attributes={"id": "previous", "class": "noprint", "href": url},
            )
        )
    if next_week:
        url = reverse(
            "schedule-week", args=[schedule.semester, schedule.student.slug, next_week]
        )
        output.append(
            cell(
                "a",
                "&raquo;",
                attributes={"id": "next", "class": "noprint", "href": url},
            )
        )

    header_cells = [cell("th", "", attributes={"class": "time"})]
    for span, date, day in timetable.header():
        content = cell("span", _escaped(day), attributes={"class": "day"})
        if date:
            content += cell(
                "span",
                _escaped(formats.date_format(date, "j M.")),
                attributes={"class": "date"},
            )
        header_cells.append(
            cell("th", content, attributes={"colspan": span if span else None})
        )

    body_rows = []
    for row_number, timetable_row in enumerate(timetable.table):
        cells = []
        for cell_group in timetable_row:
            if not cell_group:
                cells.append(
                    cell("td", cell("div", "", attributes={"class": "wrapper"}))
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
                content = ""
                if lecture:
                    title = (
                        f"{lecture.course_name} "
                        f"{formats.time_format(lecture.start, 'H:i')}-"
                        f"{formats.time_format(lecture.end, 'H:i')}"
                    )
                    if lecture.title:
                        title += f": {lecture.title}"
                    attributes["title"] = title
                    content += cell(
                        "div",
                        _escaped(lecture.alias or lecture.course_code),
                        attributes={"class": "course"},
                    )
                    room_links = []
                    if lecture.stream:
                        room_links.append(
                            cell(
                                "a",
                                _escaped(translation.gettext("Stream")),
                                attributes={"href": lecture.stream},
                            )
                        )
                    lecture_rooms = rooms.get(lecture.lecture_id, ())[:2]
                    if lecture.stream and lecture_rooms:
                        room_links.append(",")
                    for index, room_data in enumerate(lecture_rooms):
                        room_name = room_data["name"]
                        room_url = room_data["url"]
                        if room_url:
                            room_links.append(
                                cell(
                                    "a",
                                    _escaped(room_name),
                                    attributes={"href": room_url},
                                )
                            )
                        else:
                            room_links.append(_escaped(room_name))
                        if index + 1 < len(lecture_rooms):
                            room_links.append(",")
                    content += cell(
                        "div", "".join(room_links), attributes={"class": "room"}
                    )
                    content += cell(
                        "div",
                        _escaped(lecture.title or lecture.type_name or ""),
                        attributes={"class": "type"},
                    )
                if timetable_cell.get("time"):
                    content += _escaped(timetable_cell["time"]).replace(" ", "&nbsp;")
                cells.append(
                    cell(
                        "td",
                        cell("div", content, attributes={"class": "wrapper"}),
                        attributes=attributes,
                    )
                )
        body_rows.append(
            row(
                cells,
                attributes={
                    "class": f"{'odd' if row_number % 2 == 0 else 'even'}"
                    f"{' first' if row_number == 0 else ''}"
                },
            )
        )

    output.append(
        cell(
            "div",
            table(
                [
                    section("thead", [row(header_cells)]),
                    section("tbody", body_rows),
                ],
                attributes={"id": "schedule"},
            ),
            attributes={"class": "overflow"},
        )
    )
    return mark_safe("".join(output))
