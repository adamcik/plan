# encoding: utf-8

import MySQLdb

from django.db import transaction
from django.conf import settings

from plan.common.models import *

@transaction.commit_on_success
def import_db(year, semester):
    '''Retrive all lectures for a given course'''

    semester, created = Semester.objects.get_or_create(year=year, type=semester)

    mysql_setings = {
        'db': settings.TIMETABEL_DB,
        'host': settings.TIMETABEL_HOST,
        'user': settings.TIMETABEL_USER,
        'passwd': settings.TIMETABEL_PASS,
        'use_unicode': True,
    }

    db = MySQLdb.connect(**mysql_setings)

    c = db.cursor()
    c.execute("SELECT emnekode,typenavn,dag,start,slutt,uke,romnavn,larer,aktkode FROM h08_timeplan WHERE emnekode NOT LIKE '#%'")

    added_lectures = []

    for code,type,day,start,end,week,room,lecturer,groupcode in c.fetchall():
        if not code.strip():
            continue

        # Remove -1 etc. from course code
        code = ''.join(code.split('-')[:-1]).upper()

        # Get and or update course
        course, created = Course.objects.get_or_create(name=code)
        course.semesters.add(semester)

        # Load or create type:
        if type:
            type, created = Type.objects.get_or_create(name=type)

        # Figure out day mapping
        try:
            day= ['mandag', 'tirsdag', 'onsdag', 'torsdag', 'fredag'].index(day)
        except ValueError:
            print day
            continue

        # Figure out times:

        # We choose to be slightly naive and only care about which hour
        # something starts.
        start = dict(map(lambda x: (int(x[1].split(':')[0]),x[0]), Lecture.START))[int(start.split(':')[0])]
        end = dict(map(lambda x: (int(x[1].split(':')[0]),x[0]), Lecture.END))[int(end.split(':')[0])]

        # Rooms:
        rooms = []
        for r in room.split('#'):
            if r.strip():
                r, created = Room.objects.get_or_create(name=r)
                rooms.append(r)

        # Groups:
        groups = []
        c2 = db.cursor()
        c2.execute("""SELECT DISTINCT asp.studieprogramkode
                FROM h08_akt_studieprogram asp,studieprogram sp
                WHERE asp.studieprogramkode=sp.studieprogram_kode and asp.aktkode = %s""", groupcode)
        for group in c2.fetchall():
            group, created = Group.objects.get_or_create(name=group[0])
            groups.append(group)
        if not groups:
            group, created = Group.objects.get_or_create(name=Group.DEFAULT)
            groups = [group]

        # Weeks
        weeks = []
        for w in week.split(','):
            if '-' in w:
                x,y = w.split('-')
                for i in range(int(x),int(y)):
                    w2, created = Week.objects.get_or_create(number=i)
                    weeks.append(w2)
            else:
                w2, created = Week.objects.get_or_create(number=w)
                weeks.append(w2)

        # Lecturer:
        lecturers = []
        for l in lecturer.split('#'):
            if l.strip():
                lecturer, created = Lecturer.objects.get_or_create(name=l.strip())
                lecturers.append(lecturer)

        lecture_kwargs = {
            'course': course,
            'day': day,
            'start_time': start,
            'end_time': end,
            'semester': semester,
            'type': type,
        }
        if not type:
            del lecture_kwargs['type']

        lectures = Lecture.objects.filter(**lecture_kwargs)

        for lecture in lectures:
            if lecture.groups.count() == lecture.groups.filter(name__in=map(lambda g: g.name, groups)).count():
                lecture.rooms = rooms
                lecture.weeks = weeks
                lecture.lectures = lectures

                added_lectures.append(lecture.id)
        if not lectures:
            lecture = Lecture(**lecture_kwargs)
            lecture.save()

            added_lectures.append(lecture.id)

            lecture.groups = groups
            lecture.rooms = rooms
            lecture.weeks = weeks
            lecture.lectures = lecturers

    print Lecture.objects.exclude(id__in=added_lectures, semester=semester).values_list('id', flat=True)
