# Copyright 2008, 2009 Thomas Kongevold Adamcik
# 2009 IME Faculty Norwegian University of Science and Technology

# This file is part of Plan.
#
# Plan is free software: you can redistribute it and/or modify
# it under the terms of the Affero GNU General Public License as
# published by the Free Software Foundation, either version 3 of
# the License, or (at your option) any later version.
#
# Plan is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# Affero GNU General Public License for more details.
#
# You should have received a copy of the Affero GNU General Public
# License along with Plan.  If not, see <http://www.gnu.org/licenses/>.

import logging

from datetime import datetime

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import landscape, A4, A5, A6
from reportlab.platypus import Paragraph, KeepInFrame
from reportlab.platypus.tables import Table, TableStyle
from reportlab.lib.colors import HexColor
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet

styles = getSampleStyleSheet()

from django.core.urlresolvers import reverse
from django.http import HttpResponse, Http404
from django.utils.html import escape
from django.utils.translation import ugettext as _

from plan.common.models import Lecture, Semester, Room, Course
from plan.common.timetable import Timetable
from plan.common.utils import ColorMap
from plan.common.cache import get_realm, cache

outer_border = HexColor('#666666')
inner_border = HexColor('#CCCCCC')
backgrounds = [HexColor('#FFFFFF'), HexColor('#FAFAFA')]

def _tablestyle():
    table_style = TableStyle([
        ('FONT',     (0,0),  (-1,-1),'Helvetica-Bold'),
        ('FONTSIZE', (0,0),  (-1,0),  10),
        ('FONTSIZE', (0,0),  (0,-1),  8),

        ('TOPPADDING',    (0,0),  (-1,-1), 1),
        ('TOPPADDING',    (0,0),  (0,-1),  5),
        ('BOTTOMPADDING', (0,0),  (-1,-1), 1),
        ('LEFTPADDING',   (0,0),  (-1,-1), 2),
        ('RIGHTPADDING',  (0,0),  (-1,-1), 1),

        ('ALIGN',  (0,0),  (0,-1),  'CENTER'),
        ('VALIGN', (0,0),  (0,-1),  'MIDDLE'),
        ('ALIGN',  (1,0),  (-1,-1), 'LEFT'),
        ('VALIGN', (1,0),  (-1,-1), 'TOP'),

        ('LINEABOVE',  (0,1),  (-1,1),  1, outer_border),
        ('LINEBELOW',  (0,-1), (-1,-1), 1, outer_border),
        ('LINEBEFORE', (0,1),  (0,-1),  1, outer_border),
        ('LINEAFTER',  (-1,1), (-1,-1), 1, outer_border),

        ('LINEBELOW',  (0,1), (-1,-2), 0.7, inner_border),

        ('ROWBACKGROUNDS', (0,0), (-1,-1), backgrounds),
    ])

    return table_style

def pdf(request, year, semester_type, slug, size=None, week=None):
    if size is not None and size not in ['A4', 'A5', 'A6', 'A7']:
        raise Http404

    semester = Semester(year=year, type=semester_type)

    cache_realm = get_realm(semester, slug)
    response = cache.get(request.path, realm=cache_realm)

    if response and getattr(request, 'use_cache', True):
        return response

    color_map = ColorMap(hex=True)

    margin = 0.5*cm
    width, height = landscape(A5)

    width -= 2*margin
    height -= 2*margin

    time_width = 0.06 * width
    day_width = (width-time_width) / 5

    filename = '%s-%s-%s' % (year, semester.type, slug)

    if week:
        filename += '-%s' % week

    response = HttpResponse(mimetype='application/pdf')
    response['Content-Disposition'] = 'attachment; filename=%s.pdf' % filename

    lectures = Lecture.objects.get_lectures(year, semester.type, slug, week)
    rooms = Lecture.get_related(Room, lectures)
    courses = Course.objects.get_courses(year, semester.type, slug)

    for course in courses:
        color_map[course.id]

    timetable = Timetable(lectures)
    if lectures:
        timetable.place_lectures()
        timetable.do_expansion()
    timetable.insert_times()

    paragraph_style = styles['Normal']
    paragraph_style.fontName = 'Helvetica-Bold'
    paragraph_style.fontSize = 10
    paragraph_style.leading = 12

    table_style = _tablestyle()

    data = [['']]

    # Add days
    # FIXME move to timetable
    for i,day in enumerate([_('Monday'), _('Tuesday'), _('Wednesday'), _('Thursday'), _('Friday')]):
        data[0].append(day)
        if timetable.span[i] > 1:
            extra = timetable.span[i] - 1

            table_style.add('SPAN', (len(data[0])-1,0), (len(data[0])-1+extra,0))
            data[0].extend([''] * extra)

    # Convert to "simple" datastruct
    for row in timetable.table:
        data_row = []
        for cells in row:
            for cell in cells:
                time = cell.get('time', '')
                lecture = cell.get('lecture', '')

                if lecture:
                    if lecture.type and lecture.type.optional:
                        paragraph_style.fontName = 'Helvetica'

                    code= lecture.alias or lecture.course.code
                    content = [Paragraph(escape(code), paragraph_style)]
                    paragraph_style.leading = 8

                    if lecture.type:
                        content += [Paragraph(u'<font size=6>%s</font>' % lecture.type.name.replace('/', ' / '), paragraph_style)]

                    content += [Paragraph(u'<font size=6>%s</font>' % u', '.join(rooms.get(lecture.id, [])), paragraph_style)]

                    paragraph_style.leading = 12
                    paragraph_style.fontName = 'Helvetica-Bold'

                elif time:
                    content = time.replace(' - ', '\n')
                else:
                    content = ''

                if cell.get('remove', False):
                    data_row.append('')
                else:
                    data_row.append(content)

        data.append(data_row)

    # Calculate widths and line that splits days
    col_widths = [time_width]
    for w in timetable.span:
        x = len(col_widths)
        table_style.add('LINEBEFORE', (x,1),  (x,-1),  1, outer_border)

        col_widths.extend([float(day_width)/w] * w)

    # Set row heights
    row_heights  = [12]
    row_heights += [(height-8) / (len(data)-1)] * (len(data)-1)

    # Create spans, setup backgrounds and put content in KeepInFrame
    for lecture in timetable.lectures:
        offset = 0
        for o in timetable.span[:lecture['j']]:
            offset += o

        x1 = offset + lecture['k'] + 1
        y1 = lecture['i']+1

        x2 = x1 + lecture['width'] - 1
        y2 = y1 + lecture['height'] - 1

        table_style.add('SPAN', (x1,y1), (x2,y2))
        table_style.add('BACKGROUND', (x1,y1), (x2,y2),
                HexColor(color_map[lecture['l'].course_id]))

        content = data[y1][x1]
        data[y1][x1] =  KeepInFrame(col_widths[x1]*lecture['width'],
                                    row_heights[1]*lecture['height'],
                                    content, mode='shrink')

    page = canvas.Canvas(response, A4)
    page.translate(margin, A4[1]-margin)

    if 'A4' == size:
        page.translate(0.5*margin, 2.5*margin-A4[1])
        page.scale(1.414, 1.414)
        page.rotate(90)
    elif 'A6' == size:
        page.scale(0.707, 0.707)
    elif 'A7' == size:
        page.scale(0.5, 0.5)

    table = Table(data, colWidths=col_widths, rowHeights=row_heights,
            style=table_style)

    table.wrapOn(page, width, height)
    table.drawOn(page, 0,-height)

    note = request.META.get('HTTP_HOST', '').split(':')[0]

    page.setFont('Helvetica', 10)
    page.setFillColor(HexColor('#666666'))
    page.drawString(width - page.stringWidth(note) - 2, -height+2, note)

    if week:
        week_text = _('Week') + ' %s' % week
    else:
        week_text = _('All weeks')

    page.setFont('Helvetica', 8)
    page.setFillColor(HexColor('#000000'))
    page.drawString(0, -6, week_text)

    page.showPage()
    page.save()

    cache.set(request.path, response, realm=cache_realm)

    return response
