from urllib import urlopen
from xml.dom import minidom
from dateutil.parser import parse

from django.db import transaction

from plan.common.models import Exam, Course, Semester

@transaction.commit_on_success
def import_xml(year, semester, url):
    added, updated = [], []
    semester = Semester.objects.get(year=year, type=semester)

    dom = minidom.parseString(urlopen(url).read())

    for n in dom.getElementsByTagName('dato_row'):
        exam_kwargs = {}

        course_code = n.getElementsByTagName('emnekode')[0].firstChild

        exam_date = n.getElementsByTagName('dato_eksamen') \
                [0].firstChild
        exam_time = n.getElementsByTagName('klokkeslett_fremmote_tid') \
                [0].firstChild

        handout_date = n.getElementsByTagName('dato_uttak')[0].firstChild
        handout_time = n.getElementsByTagName('klokkeslett_uttak') \
                [0].firstChild

        handin_date = n.getElementsByTagName('dato_innlevering') \
                [0].firstChild
        handin_time = n.getElementsByTagName('klokkeslett_innlevering') \
                [0].firstChild

        duration = n.getElementsByTagName('varighettimer')[0].firstChild

        long_typename_key = 'vurderingskombinasjon_vurdkombnavn_bokmal'
        long_typename = n.getElementsByTagName(long_typename_key) \
                [0].firstChild
        typename = n.getElementsByTagName('vurderingsformkode') \
                [0].firstChild

        status_code = n.getElementsByTagName('vurdstatuskode') \
                [0].firstChild

        comment = n.getElementsByTagName('kommentar_eksamen') \
                [0].firstChild

        if not status_code or status_code.nodeValue != 'ORD':
            continue

        course, created = Course.objects.get_or_create(
                name=course_code.nodeValue)
        exam_kwargs['course'] = course

        if exam_date:
            exam_kwargs['exam_date'] = parse(exam_date.nodeValue).date()
        if exam_time:
            exam_kwargs['exam_time'] = parse(exam_time.nodeValue).time()

        if handout_date:
            exam_kwargs['handout_date'] = parse(handout_date.nodeValue) \
                    .date()
        if handout_time:
            exam_kwargs['handout_time'] = parse(handout_time.nodeValue) \
                    .time()

        if handin_date:
            exam_kwargs['exam_date'] = parse(handin_date.nodeValue).date()
        if handin_time:
            exam_kwargs['exam_time'] = parse(handin_time.nodeValue).time()

        if typename:
            exam_kwargs['type'] = typename.nodeValue
        else:
            exam_kwargs['type'] = ''

        try:
            exam, created = Exam.objects.get_or_create(**exam_kwargs)
        except Exam.MultipleObjectsReturned, e:
            print Exam.objects.filter(**exam_kwargs).values()
            raise e

        if created:
            print "Added exam for %s" % course.name
            added.append(exam.id)
        else:
            print "Updated exam for %s" % course.name
            updated.append(exam.id)

        if duration:
            exam.duration = duration.nodeValue

        if comment:
            exam.comment = comment.nodeValue

        if long_typename:
            exam.type_name = long_typename.nodeValue

        exam.semester = semester
        exam.save()

        n.unlink()

    to_delete = Exam.objects.exclude(id__in=added+updated). \
            filter(semester__in=[semester])

    print 'Added %d exams' % len(added)
    print 'Updated %d exams' % len(updated)
    print 'Deleting %d exams' % len(to_delete)

    to_delete.delete()
