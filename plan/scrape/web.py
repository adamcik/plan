import re

from urllib import urlopen, URLopener
from BeautifulSoup import BeautifulSoup, NavigableString

from django.db import transaction
from django.utils.http import urlquote

from plan.common.models import *

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
            courses.append(m.group(2,1))

    for name,full_name in courses:
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

        for i,td in enumerate(tr.findAll('td')):
            if i == 0:
                results[-1]['course'] = td.contents
            elif i == 2:
                results[-1]['type'] = td.contents
            elif i == 3:
                results[-1]['time'] = td.findAll(text=lambda text: isinstance(text, NavigableString))
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

        time = {}
        for t in r['time']:
            if t.startswith('Innl.:'):
                time['exam'] = parse(t.split(':', 1)[1], dayfirst=True)

            elif t.startswith('Ut:'):
                time['handout'] = parse(t.split(':', 1)[1], dayfirst=True)

            else:
                time['exam'] = parse(t, dayfirst=True)
        if r['type']:
            exam_type = r['type'][0]
        else:
            exam_type = ''

        exam = Exam(
                course=course,
                type=exam_type,
                exam_time=time.get('exam'),
                handout_time=time.get('handout', None),
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
    url  = 'http://www.ntnu.no/studieinformasjon/timeplan/h08/?emnekode=%s' % urlquote(course.encode('latin-1'))

    errors = []

    text_only = lambda text: isinstance(text, NavigableString)

    for number in [1,2,3]:
        html = ''.join(urlopen('%s-%d' % (url, number)).readlines())
        table = BeautifulSoup(html).findAll('div', 'hovedramme')[0].findAll('table')[1]

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

    type = None
    for tr in table.findAll('tr')[2:-1]:
        time, weeks, room, lecturer, groups  = [], [], [], [], []
        lecture = True

        for i,td in enumerate(tr.findAll('td')):
            # Break td loose from rest of table so that any refrences we miss
            # don't cause to big memory problems
            td.extract()

            # Loop over our td's basing our action on the td's index in the tr
            # element.
            if i == 0:
                if td.get('colspan') == '4':
                    type = td.findAll(text=text_only)
                    lecture = False

                    [t.extract() for t in type]
                    break
                else:
                    for t in td.findAll('b')[0].findAll(text=text_only):
                        t.extract()

                        day, period = t.split(' ', 1)
                        start, end = [x.strip() for x in period.split('-')]
                        time.append([day,start,end])

                    for week in td.findAll(text=re.compile('^Uke:')):
                        week.extract()
                        for w in week.replace('Uke:', '', 1).split(','):
                            if '-' in w:
                                x,y = w.split('-')
                                weeks.extend(range(int(x),int(y)))
                            else:
                                weeks.append(int(w.replace(',', '')))
            elif i == 1:
                [room.extend(a.findAll(text=text_only)) for a in td.findAll('a')]
                [r.extract() for r in room]
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
                'type': type,
                'time': time,
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
            type, created = Type.objects.get_or_create(name=r['type'][0])
        else:
            type = None

        day = ['Mandag', 'Tirsdag', 'Onsdag', 'Torsdag', 'Fredag'].index(r['time'][0][0])

        # We choose to be slightly naive and only care about which hour
        # something starts.
        start = int(r['time'][0][1].split(':')[0])
        end = int(r['time'][0][2].split(':')[0])

        start = dict(map(lambda x: (int(x[1].split(':')[0]),x[0]), Lecture.START))[start]
        end = dict(map(lambda x: (int(x[1].split(':')[0]),x[0]), Lecture.END))[end]

        lecture, created = Lecture.objects.get_or_create(
            course=course,
            day=day,
            semester=semester,
            start_time=start,
            end_time=end,
            room = room,
            type = type,
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

