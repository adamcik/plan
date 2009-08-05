#encoding: utf-8

import re
import logging
import gc

from urllib import urlopen, URLopener, urlencode
from BeautifulSoup import BeautifulSoup, NavigableString
from dateutil.parser import parse

from django.utils.http import urlquote
from django.db import connection

from plan.common.models import Lecture, Lecturer, Exam, Course, Room, Type, \
        Semester, Group, Week

logger = logging.getLogger('plan.scrape.web')

is_text = lambda text: isinstance(text, NavigableString)

def update_courses(year, semester_type):
    '''Scrape the NTNU website to retrive all available courses'''

    semester, created = Semester.objects.get_or_create(year=year, type=semester_type)

    opener = URLopener()
    opener.addheader('Accept', '*/*')

    courses = []

    for letter in u'ABCDEFGHIJKLMNOPQRSTUVWXYZÆØÅ':
        url = 'http://www.ntnu.no/studieinformasjon/timeplan/%s/?%s' % (
            semester.prefix, urlencode({'bokst': letter.encode('utf-8')}))

        logger.info('Retriving %s', url)

        try:
            html = ''.join(opener.open(url).readlines())
        except IOError, e:
            logger.error('Loading falied')
            continue

        soup = BeautifulSoup(html)

        hovedramme = soup.findAll('div', {'class': 'hovedramme'})[0]

        table = hovedramme.findAll('table', recursive=False)[0]
        table = table.findAll('table')[0]

        table.extract()
        hovedramme.extract()

        for tr in table.findAll('tr'):
            name, full_name = tr.findAll('a')

            name = name.contents[0].split('-')[0]
            full_name = full_name.contents[0]

            if full_name.endswith('(Nytt)'):
                full_name = contents.rstrip('(Nytt)')

            courses.append((name, full_name))
            
    for name, full_name in courses:
        name = name.strip().upper()
        full_name = full_name.strip()

        try:
            course = Course.objects.get(name=name)
        except Course.DoesNotExist:
            course = Course(name=name)

        if course.full_name != full_name:
            course.full_name = full_name

        logger.info("Saved course %s" % course.name)
        course.save()

    return courses

def update_lectures(year, semester_type, limit=None, prefix=None):
    '''Retrive all lectures for a given course'''

    semester, created = Semester.objects.get_or_create(year=year, type=semester_type)

    prefix = prefix or semester.prefix
    results = []
    lectures = []

    for course in Course.objects.filter(semesters__in=[semester]).distinct().order_by('name'):
        url  = 'http://www.ntnu.no/studieinformasjon/timeplan/%s/?%s' % \
                (prefix, urlencode({'emnekode': course.name.encode('latin1')}))

        table = None


        for number in [1, 2, 3]:
            final_url = '%s-%d' % (url, number)

            logger.info('Retriving %s', final_url)

            html = ''.join(urlopen(final_url).readlines())
            main = BeautifulSoup(html).findAll('div', 'hovedramme')[0]


            if not main.findAll('h1', text=lambda t: course.name in t):
                main.extract()
                del html
                del main
                continue

            table = main.findAll('table')[1]

            # Try and get rid of stuff we don't need.
            table.extract()
            main.extract()
            del html
            del main

            break

        if not table:
            continue

        lecture_type = None
        for tr in table.findAll('tr')[1:-1]:
            course_time, weeks, room, lecturer, groups  = [], [], [], [], []
            lecture = True
            tr.extract()

            for i, td in enumerate(tr.findAll('td')):
                # Break td loose from rest of table so that any refrences we miss
                # don't cause to big memory problems
                td.extract()

                # Loop over our td's basing our action on the td's index in the tr
                # element.
                if i == 0:
                    if td.get('colspan') == '4':
                        lecture_type = td.findAll(text=is_text)
                        lecture = False
                    else:
                        for t in td.findAll('b')[0].findAll(text=is_text):
                            t.extract()

                            day, period = t.split(' ', 1)
                            start, end = [x.strip() for x in period.split('-')]
                            course_time.append([day, start, end])

                        for week in td.findAll(text=re.compile('^Uke:')):
                            week.extract()
                            for w in week.replace('Uke:', '', 1).split(','):
                                if '-' in w:
                                    x, y = w.split('-')
                                    weeks.extend(range(int(x), int(y)+1))
                                else:
                                    weeks.append(int(w.replace(',', '')))
                elif i == 1:
                    for a in td.findAll('a'):
                        room.extend(a.findAll(text=is_text))
                    for r in room:
                        r.extract()
                elif i == 2:
                    for l in td.findAll(text=is_text):
                        l.extract()

                        lecturer.append(l.replace('&nbsp;', ''))
                elif i == 3:
                    for g in td.findAll(text=is_text):
                        if g.replace('&nbsp;','').strip():
                            g.extract()

                            groups.append(g)

                del td
            del tr

            if lecture:
                results.append({
                    'type': lecture_type,
                    'time': course_time,
                    'weeks': weeks,
                    'room': room,
                    'lecturer': lecturer,
                    'groups': groups,
                })

        del table

    for r in results:
        connection.queries = connection.queries[-5:]

        if r['type']:
            name = unicode(r['type'][0])
            lecture_type, created = Type.objects.get_or_create(name=name)
        else:
            lecture_type = None

        day = ['Mandag', 'Tirsdag', 'Onsdag', 'Torsdag', 'Fredag']. \
                index(r['time'][0][0])

        start = parse(r['time'][0][1]).time()
        end = parse(r['time'][0][2]).time()

        lecture, created = Lecture.objects.get_or_create(
            course=course,
            day=day,
            semester=semester,
            start=start,
            end=end,
            type = lecture_type,
        )

        if not created:
            lecture.rooms.clear()
            lecture.weeks.clear()
            lecture.lecturers.clear()

        if r['room']:
            for room in r['room']:
                name = unicode(room)
                room, created = Room.objects.get_or_create(name=name)
                lecture.rooms.add(room)

        if r['groups']:
            for g in r['groups']:
                name = unicode(g)
                group, created = Group.objects.get_or_create(name=name)
                lecture.groups.add(group)
        else:
            group, created = Group.objects.get_or_create(name=Group.DEFAULT)
            lecture.groups.add(group)

        for w in  r['weeks']:
            week, created = Week.objects.get_or_create(number=w)
            lecture.weeks.add(w)

        for l in r['lecturer']:
            if l.strip():
                name = unicode(l)
                lecturer, created = Lecturer.objects.get_or_create(name=name)
                lecture.lecturers.add(lecturer)

        lecture.save()
        lectures.append(lecture.id)

        logger.info('Saved %s' % lecture)

        del lecture
        del r

    return Lecture.objects.filter(id__in=lectures)
