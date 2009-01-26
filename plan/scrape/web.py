import re

from urllib import urlopen, URLopener
from BeautifulSoup import BeautifulSoup, NavigableString
from dateutil.parser import parse

from django.db import transaction
from django.utils.http import urlquote

from plan.common.models import Lecture, Lecturer, Exam, Course, Room, Type, \
        Semester, Group, Week

is_text = lambda text: isinstance(text, NavigableString)

@transaction.commit_on_success
def scrape_courses():
    '''Scrape the NTNU website to retrive all available courses'''

    opener = URLopener()
    opener.addheader('Accept', '*/*')

    html = ''.join(opener.open('http://www.ntnu.no/studier/emner').readlines())
    soup = BeautifulSoup(html)

    courses = []
    for a in soup.findAll('div', id="browseForm")[0].findAll('a'):
        contents = a.contents[0].strip()

        if contents.endswith('(Nytt)'):
            contents = contents[:-len('(Nytt)')]

        m = re.match(r'^\s*(.+)\((.+)\)\s*$', contents)

        if m:
            courses.append(m.group(2, 1))

    for name, full_name in courses:
        try:
            course = Course.objects.get(name=name.strip().upper())
        except Course.DoesNotExist:
            course = Course(name=name.strip().upper())

        if course.full_name != full_name.strip():
            course.full_name = full_name.strip()

        course.save()

    # FIXME delete unimported courses

    return courses


@transaction.commit_on_success
def scrape_exams():
    # FIXME
    url = 'http://www.ntnu.no/eksamen/plan/09v/'

    html = ''.join(urlopen(url).readlines())
    soup = BeautifulSoup(html)

    main = soup.findAll('div', 'hovedramme')[0]

    results = []
    for tr in main.findAll('tr')[4:]:
        results.append({})

        for i, td in enumerate(tr.findAll('td')):
            if i == 0:
                results[-1]['course'] = td.contents
            elif i == 2:
                results[-1]['type'] = td.contents
            elif i == 3:
                results[-1]['time'] = td.findAll(text=is_text)
            elif i == 4:
                results[-1]['duration'] = td.contents
            elif i == 5:
                results[-1]['comment'] = td.contents

    for r in results:
        course, created = Course.objects.get_or_create(name=r['course'][0])

        if r['duration']:
            duration = r['duration'][0]
        else:
            duration = None

        if r['comment']:
            comment = r['comment'][0]
        else:
            comment = ''

        exam_time = {}
        for t in r['time']:
            if t.startswith('Innl.:'):
                exam_time['exam'] = parse(t.split(':', 1)[1], dayfirst=True)

            elif t.startswith('Ut:'):
                exam_time['handout'] = parse(t.split(':', 1)[1], dayfirst=True)

            else:
                exam_time['exam'] = parse(t, dayfirst=True)
        if r['type']:
            exam_type = r['type'][0]
        else:
            exam_type = ''

        exam = Exam(
                course=course,
                type=exam_type,
                exam_time=exam_time.get('exam'),
                handout_time=exam_time.get('handout', None),
                comment=comment,
                duration=duration
               )
        exam.save()

    return results

# FIXME take semester as parameter
@transaction.commit_on_success
def scrape_course(course):
    '''Retrive all lectures for a given course'''

    course = course.upper().strip()

    # FIXME based on semester
    url  = 'http://www.ntnu.no/studieinformasjon/timeplan/h08/?emnekode=%s' % \
            urlquote(course.encode('latin-1'))

    errors = []

    text_only = lambda text: isinstance(text, NavigableString)

    for number in [1, 2, 3]:
        html = ''.join(urlopen('%s-%d' % (url, number)).readlines())
        table = BeautifulSoup(html).findAll('div', 'hovedramme')[0]. \
                    findAll('table')[1]

        # Try and get rid of stuff we don't need.
        table.extract()
        del html

        results = []

        try:
            title = table.findAll('h2')[0].contents[0].split('-')[2].strip()

            errors = []
            break

        except IndexError:
            errors.append(('Course does not exsist', '%s-%d' % (url, number)))
            del table

    if errors:
        raise Exception(errors)

    lecture_type = None
    for tr in table.findAll('tr')[2:-1]:
        course_time, weeks, room, lecturer, groups  = [], [], [], [], []
        lecture = True

        for i, td in enumerate(tr.findAll('td')):
            # Break td loose from rest of table so that any refrences we miss
            # don't cause to big memory problems
            td.extract()

            # Loop over our td's basing our action on the td's index in the tr
            # element.
            if i == 0:
                if td.get('colspan') == '4':
                    lecture_type = td.findAll(text=text_only)
                    lecture = False

                    for t in lecture_type:
                        t.extract()
                    break
                else:
                    for t in td.findAll('b')[0].findAll(text=text_only):
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
                    room.extend(a.findAll(text=text_only))
                for r in room:
                    r.extract()
            elif i == 2:
                for l in td.findAll(text=text_only):
                    l.extract()

                    lecturer.append(l.replace('&nbsp;', ''))
            elif i == 3:
                for g in td.findAll(text=text_only):
                    if g.replace('&nbsp;','').strip():
                        g.extract()

                        groups.append(g)

        if lecture:
            results.append({
                'type': lecture_type,
                'time': course_time,
                'weeks': weeks,
                'room': room,
                'lecturer': lecturer,
                'groups': groups,
                'title': title,
            })

    del table

    semester = Semester.objects.all()[0]
    course, created = Course.objects.get_or_create(name=course.upper())

    for r in results:
        if not course.full_name:
            course.full_name = r['title']
            course.save()

        if r['room']:
            room, created = Room.objects.get_or_create(name=r['room'][0])
        else:
            room = None

        if r['type']:
            lecture_type, created = Type.objects.get_or_create(name=r['type'][0])
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
            room = room,
            type = lecture_type,
        )
        r['id'] = lecture.id

        if r['groups']:
            for g in r['groups']:
                group, created = Group.objects.get_or_create(name=g)
                lecture.groups.add(group)
        else:
            group, created = Group.objects.get_or_create(name=Group.DEFAULT)
            lecture.groups.add(group)

        for w in  r['weeks']:
            week, created = Week.objects.get_or_create(number=w)
            lecture.weeks.add(w)

        for l in r['lecturer']:
            if l.strip():
                lecturer, created = Lecturer.objects.get_or_create(name=l)
                lecture.lecturers.add(lecturer)

        lecture.save()

    return results

