# encoding: utf-8

import MySQLdb
from decimal import Decimal

from django.db import transaction
from django.conf import settings

from plan.settings_msqyl import *
from plan.common.models import Course, Lecture, Lecturer, Semester, Group, \
        Type, Week, Room

@transaction.commit_on_success
def import_db(year, semester):
    '''Retrive all lectures for a given course'''

    semester, created = Semester.objects.get_or_create(year=year, type=semester)

    mysql_setings = {
        'db': TIMETABEL_DB,
        'host': TIMETABEL_HOST,
        'user': TIMETABEL_USER,
        'passwd': TIMETABEL_PASS,
        'use_unicode': True,
    }

    db = MySQLdb.connect(**mysql_setings)

    c = db.cursor()

    c.execute("""
        SELECT emnekode,typenavn,dag,start,slutt,uke,romnavn,larer,aktkode
        FROM h08_timeplan WHERE emnekode NOT LIKE '#%'
    """)

    added_lectures = []

    for l in Lecture.objects.all():
        l.rooms.clear()
        l.weeks.clear()
        l.lecturers.clear()

    for row in c.fetchall():
        code, course_type, day, start, end, week, room, lecturer, groupcode = row
        if not code.strip():
            continue

        # Remove -1 etc. from course code
        code = ''.join(code.split('-')[:-1]).upper()

        # Get and or update course
        course, created = Course.objects.get_or_create(name=code)
        course.semesters.add(semester)

        # Load or create type:
        if course_type:
            course_type, created = Type.objects.get_or_create(name=course_type)

        # Figure out day mapping
        try:
            day = ['mandag', 'tirsdag', 'onsdag', 'torsdag', 'fredag'].index(day)
        except ValueError:
            print day
            continue

        # Figure out times:

        # We choose to be slightly naive and only care about which hour
        # something starts.
        start = dict(map(lambda x: (int(x[1].split(':')[0]), x[0]),
                Lecture.START))[int(start.split(':')[0])]
        end = dict(map(lambda x: (int(x[1].split(':')[0]), x[0]),
                Lecture.END))[int(end.split(':')[0])]

        # Rooms:
        rooms = []
        for r in room.split('#'):
            if r.strip():
                r, created = Room.objects.get_or_create(name=r)
                rooms.append(r)

        # Groups:
        groups = []
        c2 = db.cursor()
        c2.execute("""
                SELECT DISTINCT asp.studieprogramkode
                FROM h08_akt_studieprogram asp,studieprogram sp
                WHERE asp.studieprogramkode=sp.studieprogram_kode
                AND asp.aktkode = %s
            """, groupcode)
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
                x, y = w.split('-')
                for i in range(int(x), int(y)):
                    w2, created = Week.objects.get_or_create(number=i)
                    weeks.append(w2)
            else:
                w2, created = Week.objects.get_or_create(number=w)
                weeks.append(w2)

        # Lecturer:
        lecturers = []
        for l in lecturer.split('#'):
            if l.strip():
                lecturer, created = Lecturer.objects.get_or_create(
                        name=l.strip())
                lecturers.append(lecturer)

        lecture_kwargs = {
            'course': course,
            'day': day,
            'start_time': start,
            'end_time': end,
            'semester': semester,
            'type': course_type,
        }
        if not course_type:
            del lecture_kwargs['type']

        lectures = Lecture.objects.filter(**lecture_kwargs)
        added = False

        for lecture in lectures:
            psql_set = set(lecture.groups.values_list('id', flat=True))
            mysql_set = set(map(lambda g: g.id, groups))

            if psql_set == mysql_set:
                # Append data
                for r in rooms:
                    lecture.rooms.add(r)
                for w in weeks:
                    lecture.weeks.add(w)
                for l in lecturers:
                    lecture.lecturers.add(l)

                added_lectures.append(lecture.id)
                added = True
                break

        if not added:
            lecture = Lecture(**lecture_kwargs)
            lecture.save()

            added_lectures.append(lecture.id)

            # Simply set data since we are saving new lecture
            lecture.groups = groups
            lecture.rooms = rooms
            lecture.weeks = weeks
            lecture.lecturers = lecturers

    print Lecture.objects.exclude(id__in=added_lectures,
            semester=semester).values_list('id', flat=True)

    c.execute("""SELECT emnekode,emnenavn,vekt FROM h08_fs_emne WHERE emnekode
            NOT LIKE '#%'""")

    for code, name, points in c.fetchall():
        if not code.strip():
            continue

        course, created = Course.objects.get_or_create(
                name=''.join(code.split('-')[:-1]).upper().strip())

        print points
        if points:
            course.points = Decimal(points.strip().replace(',', '.'))
        course.full_name = name
        course.save()

        if created:
            print "Added course %s" % course.name
        else:
            print "Updated course %s" % course.name
