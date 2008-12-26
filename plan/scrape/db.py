# encoding: utf-8

import re
import MySQLdb
from decimal import Decimal

from django.db import transaction
from django.conf import settings

from plan.settings_mysql import *
from plan.common.models import Course, Lecture, Lecturer, Semester, Group, \
        Type, Week, Room

@transaction.commit_on_success
def import_db(year, semester_type, prefix=None):
    '''Retrive all lectures for a given course'''

    semester, created = Semester.objects.get_or_create(year=year, type=semester_type)

    if not prefix:
        if semester_type == Semester.SPRING:
            prefix = 'v%s' % str(year)[-2:]
        else:
            prefix = 'h%s' % str(year)[-2:]

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
        FROM %s_timeplan WHERE emnekode NOT LIKE '#%%'
    """ % prefix)

    added_lectures = []

    for l in Lecture.objects.filter(semester=semester):
        l.rooms.clear()
        l.weeks.clear()
        l.lecturers.clear()

    for row in c.fetchall():
        code, course_type, day, start, end, week, room, lecturer, groupcode = row
        if not code.strip():
            continue

        # Remove -1 etc. from course code
        code = '-'.join(code.split('-')[:-1]).upper()

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
            print "Could not add %s - %s on %s for %s" % (start, end, day, course)
            continue

        # Figure out times:

        # We choose to be slightly naive and only care about which hour
        # something starts.
        try:
            start_slot = dict(map(lambda x: (int(x[1].split(':')[0]), x[0]),
                    Lecture.START))[int(start.split(':')[0])]
            end_slot = dict(map(lambda x: (int(x[1].split(':')[0]), x[0]),
                    Lecture.END))[int(end.split(':')[0])]
        except KeyError, e:
            if int(end.split(':')[0]) == 8:
                print "Converting %s to 09:00 for %s" % (end, course)
                end_slot = 9
            elif int(end.split(':')[0]) == 0:
                print "Converting %s to 20:00 for %s" % (end, course)
                end_slot = Lecture.END[-1][0]
            else:
                print "Could not add %s - %s on %s for %s" % (start, end, day, course)
                continue

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
                FROM %s_akt_studieprogram asp,studieprogram sp
                WHERE asp.studieprogramkode=sp.studieprogram_kode
                AND asp.aktkode = %%s
            """ % prefix, groupcode)
        for group in c2.fetchall():
            group, created = Group.objects.get_or_create(name=group[0])
            groups.append(group)

        if not groups:
            group, created = Group.objects.get_or_create(name=Group.DEFAULT)
            groups = [group]

        # Weeks
        weeks = []
        for w in re.split(r',? ', week):
            if '-' in w:
                x, y = w.split('-')
                for i in range(int(x), int(y)+1):
                    w2, created = Week.objects.get_or_create(number=i)
                    weeks.append(w2)
            elif w.isdigit():
                w2, created = Week.objects.get_or_create(number=w)
                weeks.append(w2)
            else:
                print "Messed up week '%s'" % w

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
            'start_time': start_slot,
            'end_time': end_slot,
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
                lecture.rooms = rooms
                lecture.weeks = weeks
                lecture.lecturers = lecturers

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

        lecture.start = start
        lecture.end = end

    to_remove =  Lecture.objects.exclude(id__in=added_lectures). \
            filter(semester=semester).values_list('id', flat=True)

    c.execute("""SELECT emnekode,emnenavn,vekt FROM %s_fs_emne WHERE emnekode
            NOT LIKE '#%%'""" % prefix)

    for code, name, points in c.fetchall():
        if not code.strip():
            continue

        code = ''.join(code.split('-')[:-1]).upper().strip()

        if name[0] in ['"', "'"] and name[0] == name[-1]:
            name = name[1:-1]

        course, created = Course.objects.get_or_create(name=code)

        if points:
            course.points = Decimal(points.strip().replace(',', '.'))
        course.full_name = name
        course.save()

        if created:
            print "Added course %s" % course.name
        else:
            print "Updated course %s" % course.name

    return to_remove
