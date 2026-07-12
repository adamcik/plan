# This file is part of the plan timetable generator, see LICENSE for details.

from http import HTTPStatus

from reportlab import platypus
from reportlab.lib import colors, pagesizes, styles, units
from reportlab.pdfgen import canvas
from reportlab.platypus import tables

from django import http, shortcuts
from django.utils import dateformat, html, translation

from plan.common import utils
from plan.common.models import Course, Lecture, Room
from plan.common.models import Student
from plan.common.snapshot import (
    ScheduleSnapshot,
    ScheduleSnapshotNotFound,
    get_schedule_snapshot,
)
from plan.common.templatetags.title import render_title
from plan.common.timetable import Timetable
from plan.common.utils import ColorMap

outer_border = colors.HexColor("#666666")
inner_border = colors.HexColor("#CCCCCC")
backgrounds = [colors.HexColor("#FFFFFF"), colors.HexColor("#FAFAFA")]

default_styles = styles.getSampleStyleSheet()

CELL_LEFT_PADDING = 2
CELL_RIGHT_PADDING = 1

_ = translation.gettext


def _tablestyle():
    table_style = tables.TableStyle(
        [
            ("FONT", (0, 0), (-1, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 10),  # title
            ("FONTSIZE", (0, 1), (0, -1), 8),  # days
            ("FONTSIZE", (0, 1), (-1, 1), 8),  # times
            ("TOPPADDING", (0, 0), (-1, -1), 1),
            ("TOPPADDING", (0, 0), (0, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
            ("LEFTPADDING", (0, 0), (-1, -1), CELL_LEFT_PADDING),
            ("RIGHTPADDING", (0, 0), (-1, -1), CELL_RIGHT_PADDING),
            ("ALIGN", (0, 0), (0, -1), "CENTER"),
            ("VALIGN", (0, 0), (0, -1), "MIDDLE"),
            ("ALIGN", (1, 0), (-1, -1), "LEFT"),
            ("VALIGN", (1, 0), (-1, -1), "TOP"),
            ("LINEABOVE", (0, 2), (-1, 2), 1, outer_border),
            ("LINEBELOW", (0, -1), (-1, -1), 1, outer_border),
            ("LINEBEFORE", (0, 2), (0, -1), 1, outer_border),
            ("LINEAFTER", (-1, 2), (-1, -1), 1, outer_border),
            ("LINEBELOW", (0, 1), (-1, -2), 0.7, inner_border),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), backgrounds),
        ]
    )

    return table_style


def pdf(request, semester, slug, size=None, week=None):
    try:
        snapshot = get_schedule_snapshot(semester, slug)
    except ScheduleSnapshotNotFound:
        snapshot = ScheduleSnapshot(
            semester=semester,
            student=Student(slug=slug),
        )

    if size is not None and size not in ["A4", "A5", "A6", "A7"]:
        raise http.Http404()

    if snapshot.student is None:
        raise http.Http404

    filename = (
        f"{snapshot.semester.year}-{snapshot.semester.slug}-{snapshot.student.slug}"
    )

    if week:
        week = int(week)
        filename += "-%s" % week

    route = str(request.resolver_match.url_name)
    path = request.path_info
    cache_key = utils.response_cache_key(route, snapshot.freshness_key(), path)
    headers = utils.build_validator_headers(
        cache_key=cache_key,
        last_modified=snapshot.last_modified,
        extra_headers={"X-Robots-Tag": "noindex, nofollow"},
    )
    response = utils.check_not_modified(request, snapshot.last_modified, headers)
    if response:
        return response

    response = http.HttpResponse(content_type="application/pdf")
    utils.apply_response_headers(response, headers)
    response["Content-Disposition"] = "attachment; filename=%s.pdf" % filename

    color_map = ColorMap(hex=True)

    margin = 0.5 * units.cm
    width, height = pagesizes.landscape(pagesizes.A5)

    width -= 2 * margin
    height -= 2 * margin

    time_width = 0.06 * width
    day_width = (width - time_width) / 5

    # NOTE: This could be cached, and shared with schedule, but to be honest I
    # doubt it is worth it for this code path.
    lectures = Lecture.objects.get_lectures_data(
        snapshot.semester.id,
        snapshot.student.id,
    )
    lecture_ids = [lecture.lecture_id for lecture in lectures]
    rooms = Lecture.get_related(Room, lecture_ids)
    courses = Course.objects.get_courses(
        snapshot.semester.year,
        snapshot.semester.type,
        snapshot.student.slug,
    )

    for course in courses:
        color_map[course.id]

    timetable = Timetable(lectures)
    if lectures:
        timetable.place_lectures(week)
        timetable.do_expansion()
    timetable.insert_times()
    if week:
        timetable.set_week(snapshot.semester.year, week)

    paragraph_style = default_styles["Normal"]
    paragraph_style.fontName = "Helvetica-Bold"
    paragraph_style.fontSize = 10
    paragraph_style.leading = 12

    table_style = _tablestyle()

    title = render_title(
        snapshot.semester,
        snapshot.student.slug,
        week,
    )
    data = [[platypus.Paragraph(title, paragraph_style)]]
    data[-1].extend([""] * sum(timetable.span))
    table_style.add("SPAN", (0, 0), (-1, 0))

    # Add days
    data.append([""])
    for span, date, name in timetable.header():
        if date:
            data[-1].append(dateformat.format(date, "l - j M."))
        else:
            data[-1].append(str(name))
        if span > 1:
            extra = span - 1
            table_style.add(
                "SPAN", (len(data[-1]) - 1, 2), (len(data[-1]) - 1 + extra, 2)
            )
            data[-1].extend([""] * extra)

    # Convert to "simple" datastruct
    for row in timetable.table:
        data_row = []
        for cells in row:
            for cell in cells:
                time = cell.get("time", "")
                lecture = cell.get("lecture", "")

                if lecture:
                    if lecture.type_optional:
                        paragraph_style.fontName = "Helvetica"

                    code = lecture.alias or lecture.course_code
                    content = [platypus.Paragraph(html.escape(code), paragraph_style)]
                    paragraph_style.leading = 8

                    if lecture.type_name:
                        content += [
                            platypus.Paragraph(
                                "<font size=6>%s</font>"
                                % lecture.type_name.replace("/", " / "),
                                paragraph_style,
                            )
                        ]

                        content += [
                            platypus.Paragraph(
                                "<font size=6>%s</font>"
                                % ", ".join(rooms.get(lecture.lecture_id, [])),
                                paragraph_style,
                            )
                        ]

                    paragraph_style.leading = 12
                    paragraph_style.fontName = "Helvetica-Bold"

                elif time:
                    content = time.replace(" - ", "\n")
                else:
                    content = ""

                if cell.get("remove", False):
                    data_row.append("")
                else:
                    data_row.append(content)

        data.append(data_row)

    # Calculate widths and line that splits days
    col_widths = [time_width]
    for w in timetable.span:
        x = len(col_widths)
        table_style.add("LINEBEFORE", (x, 2), (x, -1), 1, outer_border)

        col_widths.extend([float(day_width) / w] * w)

    if any(
        col_width < CELL_LEFT_PADDING + CELL_RIGHT_PADDING
        for col_width in col_widths[1:]
    ):
        response = shortcuts.render(
            request,
            "error.html",
            {
                "error_title": _("Unable to export PDF"),
                "error_message": _(
                    "This timetable has too many simultaneous activities to export as PDF."
                ),
            },
            status=HTTPStatus.UNPROCESSABLE_ENTITY,
        )
        utils.apply_response_headers(response, headers)
        return response

    # Set row heights
    row_heights = [16, 12]
    row_heights += [(height - (8 * 2)) / (len(data) - 2)] * (len(data) - 2)

    # Create spans, setup backgrounds and put content in KeepInFrame
    for lecture in timetable.lectures:
        offset = 0
        for o in timetable.span[: lecture["j"]]:
            offset += o

        x1 = offset + lecture["k"] + 1
        y1 = lecture["i"] + 2

        x2 = x1 + lecture["width"] - 1
        y2 = y1 + lecture["height"] - 1

        table_style.add("SPAN", (x1, y1), (x2, y2))
        table_style.add(
            "BACKGROUND",
            (x1, y1),
            (x2, y2),
            colors.HexColor(color_map[lecture["l"].course_id]),
        )

        content = data[y1][x1]
        data[y1][x1] = platypus.KeepInFrame(
            col_widths[x1] * lecture["width"],
            row_heights[2] * lecture["height"],
            content,
            mode="shrink",
        )

    page = canvas.Canvas(response, pagesizes.A4)
    page.translate(margin, pagesizes.A4[1] - margin)

    if "A4" == size:
        page.translate(0.5 * margin, 2.5 * margin - pagesizes.A4[1])
        page.scale(1.414, 1.414)
        page.rotate(90)
    elif "A6" == size:
        page.scale(0.707, 0.707)
    elif "A7" == size:
        page.scale(0.5, 0.5)

    table = tables.Table(
        data, colWidths=col_widths, rowHeights=row_heights, style=table_style
    )

    table.wrapOn(page, width, height)
    table.drawOn(page, 0, -height)

    note = request.headers.get("Host", "").split(":")[0]

    page.setFont("Helvetica", 10)
    page.setFillColor(colors.HexColor("#666666"))
    page.drawString(width - page.stringWidth(note) - 2, -height + 2, note)

    page.showPage()
    page.save()

    return response
