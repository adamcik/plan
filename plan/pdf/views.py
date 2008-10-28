from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import landscape, A4
from reportlab.platypus.tables import Table, TableStyle
from reportlab.lib.colors import HexColor
from reportlab.lib.units import cm

from pprint import pprint

from django.http import HttpResponse
from django.core.cache import cache

from plan.common.models import Lecture, Semester, Room
from plan.common.timetable import Timetable
from plan.common.utils import ColorMap

def pdf(request, year, semester_type, slug):
    semester = Semester(year=year, type=semester_type)

    response = cache.get(request.path)

    if response and 'no-cache' not in request.GET:
        return response

    color_map = ColorMap(hex=True)

    margin = 0.5*cm
    width, height = landscape(A4)

    width -= 2*margin
    height -= 2*margin

    time_width = 0.085 * width
    day_width = (width-time_width) / 5

    filename = '%s-%s-%s' % (year, semester.get_type_display(), slug)

    response = HttpResponse(mimetype='application/pdf')
    response['Content-Disposition'] = 'attachment; filename=%s.pdf' % filename

    lectures = Lecture.objects.get_lectures(year, semester.type, slug)
    rooms = Lecture.get_related(Room, lectures)

    timetable = Timetable(lectures, rooms)
    if lectures:
        timetable.place_lectures()
        timetable.do_expansion()
    timetable.insert_times()

    page = canvas.Canvas(response, landscape(A4))

    data = [['']]

    for i,day in enumerate(['Monday', 'Tuesday', 'Wednsday', 'Thursday', 'Friday']):
        data[0].append(day)
        if timetable.span[i] > 1:
            extra = timetable.span[i] - 1
            data[0].extend([''] * extra)

    for row in timetable.table:
        data_row = []
        for cells in row:
            for cell in cells:
                time = cell.get('time', '')
                lecture = cell.get('lecture', '')

                if lecture:
                    lecture = lecture.alias or lecture.course

                if cell.get('remove', False):
                    data_row.append('removed')
                else:
                    data_row.append(str(time or lecture or ''))

        data.append(data_row)

    style = TableStyle([
        ('ALIGN',      (0,0),  (-1,-1), 'LEFT'),
        ('VALIGN',     (0,0),  (-1,-1), 'TOP'),
        ('LINEABOVE',  (0,1),  (-1,1),  1, HexColor('#666666')),
        ('LINEBELOW',  (0,-1), (-1,-1), 1, HexColor('#666666')),
        ('LINEBEFORE', (0,1),  (0,-1),  1, HexColor('#666666')),
        ('LINEAFTER',  (-1,1), (-1,-1), 1, HexColor('#666666')),

        ('LINEBELOW',  (0,1), (-1,-2), 1, HexColor('#CCCCCC')),

        ('ROWBACKGROUNDS', (0,0), (-1,-1), [HexColor('#FFFFFF'), HexColor('#FAFAFA')]),
    ])

    col_widths = [time_width]
    for width in timetable.span:
        x = len(col_widths)
        style.add('LINEBEFORE', (x,1),  (x,-1),  1, HexColor('#666666'))
        col_widths.extend([float(day_width)/width] * width)

    row_heights  = [14]
    row_heights += [(height-14) / (len(data)-1)] * (len(data)-1)


    for lecture in timetable.lectures:
        offset = 0
        for o in timetable.span[:lecture['j']]:
            offset += o

        x1 = offset + lecture['k'] + 1
        y1 = lecture['i']+1

        x2 = x1 + lecture['width'] - 1
        y2 = y1 + lecture['height'] - 1

        style.add('SPAN', (x1,y1), (x2,y2))
        style.add('BACKGROUND', (x1,y1), (x2,y2), 
                HexColor(color_map[lecture['course']]))

    print style

    table = Table(data, colWidths=col_widths, rowHeights=row_heights, style=style)
    table.wrapOn(page, width, height)
    table.drawOn(page, margin, margin)

    page.showPage()
    page.save()

    cache.set(request.path, response)
    return response
