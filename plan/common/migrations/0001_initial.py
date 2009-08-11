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

from south.db import db
from django.db import models
from plan.common.models import *

class Migration:
    
    def forwards(self, orm):
        
        # Adding model 'Type'
        db.create_table('common_type', (
            ('id', orm['common.Type:id']),
            ('name', orm['common.Type:name']),
            ('optional', orm['common.Type:optional']),
        ))
        db.send_create_signal('common', ['Type'])
        
        # Adding model 'Course'
        db.create_table('common_course', (
            ('id', orm['common.Course:id']),
            ('name', orm['common.Course:name']),
            ('full_name', orm['common.Course:full_name']),
            ('url', orm['common.Course:url']),
            ('points', orm['common.Course:points']),
        ))
        db.send_create_signal('common', ['Course'])
        
        # Adding model 'Semester'
        db.create_table('common_semester', (
            ('id', orm['common.Semester:id']),
            ('year', orm['common.Semester:year']),
            ('type', orm['common.Semester:type']),
        ))
        db.send_create_signal('common', ['Semester'])
        
        # Adding model 'Lecturer'
        db.create_table('common_lecturer', (
            ('id', orm['common.Lecturer:id']),
            ('name', orm['common.Lecturer:name']),
        ))
        db.send_create_signal('common', ['Lecturer'])
        
        # Adding model 'Group'
        db.create_table('common_group', (
            ('id', orm['common.Group:id']),
            ('name', orm['common.Group:name']),
        ))
        db.send_create_signal('common', ['Group'])
        
        # Adding model 'Deadline'
        db.create_table('common_deadline', (
            ('id', orm['common.Deadline:id']),
            ('userset', orm['common.Deadline:userset']),
            ('date', orm['common.Deadline:date']),
            ('time', orm['common.Deadline:time']),
            ('task', orm['common.Deadline:task']),
        ))
        db.send_create_signal('common', ['Deadline'])
        
        # Adding model 'Week'
        db.create_table('common_week', (
            ('id', orm['common.Week:id']),
            ('number', orm['common.Week:number']),
        ))
        db.send_create_signal('common', ['Week'])
        
        # Adding model 'Room'
        db.create_table('common_room', (
            ('id', orm['common.Room:id']),
            ('name', orm['common.Room:name']),
        ))
        db.send_create_signal('common', ['Room'])
        
        # Adding model 'UserSet'
        db.create_table('common_userset', (
            ('id', orm['common.UserSet:id']),
            ('slug', orm['common.UserSet:slug']),
            ('course', orm['common.UserSet:course']),
            ('semester', orm['common.UserSet:semester']),
            ('name', orm['common.UserSet:name']),
            ('added', orm['common.UserSet:added']),
        ))
        db.send_create_signal('common', ['UserSet'])
        
        # Adding model 'Exam'
        db.create_table('common_exam', (
            ('id', orm['common.Exam:id']),
            ('exam_date', orm['common.Exam:exam_date']),
            ('exam_time', orm['common.Exam:exam_time']),
            ('handout_date', orm['common.Exam:handout_date']),
            ('handout_time', orm['common.Exam:handout_time']),
            ('duration', orm['common.Exam:duration']),
            ('comment', orm['common.Exam:comment']),
            ('type', orm['common.Exam:type']),
            ('type_name', orm['common.Exam:type_name']),
            ('course', orm['common.Exam:course']),
            ('semester', orm['common.Exam:semester']),
        ))
        db.send_create_signal('common', ['Exam'])
        
        # Adding model 'Lecture'
        db.create_table('common_lecture', (
            ('id', orm['common.Lecture:id']),
            ('course', orm['common.Lecture:course']),
            ('semester', orm['common.Lecture:semester']),
            ('day', orm['common.Lecture:day']),
            ('start', orm['common.Lecture:start']),
            ('end', orm['common.Lecture:end']),
            ('type', orm['common.Lecture:type']),
        ))
        db.send_create_signal('common', ['Lecture'])
        
        # Adding ManyToManyField 'Lecture.weeks'
        db.create_table('common_lecture_weeks', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('lecture', models.ForeignKey(orm.Lecture, null=False)),
            ('week', models.ForeignKey(orm.Week, null=False))
        ))
        
        # Adding ManyToManyField 'Lecture.rooms'
        db.create_table('common_lecture_rooms', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('lecture', models.ForeignKey(orm.Lecture, null=False)),
            ('room', models.ForeignKey(orm.Room, null=False))
        ))
        
        # Adding ManyToManyField 'Lecture.groups'
        db.create_table('common_lecture_groups', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('lecture', models.ForeignKey(orm.Lecture, null=False)),
            ('group', models.ForeignKey(orm.Group, null=False))
        ))
        
        # Adding ManyToManyField 'Lecture.lecturers'
        db.create_table('common_lecture_lecturers', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('lecture', models.ForeignKey(orm.Lecture, null=False)),
            ('lecturer', models.ForeignKey(orm.Lecturer, null=False))
        ))
        
        # Adding ManyToManyField 'UserSet.exclude'
        db.create_table('common_userset_exclude', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('userset', models.ForeignKey(orm.UserSet, null=False)),
            ('lecture', models.ForeignKey(orm.Lecture, null=False))
        ))
        
        # Adding ManyToManyField 'Course.semesters'
        db.create_table('common_course_semesters', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('course', models.ForeignKey(orm.Course, null=False)),
            ('semester', models.ForeignKey(orm.Semester, null=False))
        ))
        
        # Adding ManyToManyField 'UserSet.groups'
        db.create_table('common_userset_groups', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('userset', models.ForeignKey(orm.UserSet, null=False)),
            ('group', models.ForeignKey(orm.Group, null=False))
        ))
        
        # Creating unique_together for [year, type] on Semester.
        db.create_unique('common_semester', ['year', 'type'])
        
        # Creating unique_together for [slug, course, semester] on UserSet.
        db.create_unique('common_userset', ['slug', 'course_id', 'semester_id'])
        
    
    
    def backwards(self, orm):
        
        # Deleting model 'Type'
        db.delete_table('common_type')
        
        # Deleting model 'Course'
        db.delete_table('common_course')
        
        # Deleting model 'Semester'
        db.delete_table('common_semester')
        
        # Deleting model 'Lecturer'
        db.delete_table('common_lecturer')
        
        # Deleting model 'Group'
        db.delete_table('common_group')
        
        # Deleting model 'Deadline'
        db.delete_table('common_deadline')
        
        # Deleting model 'Week'
        db.delete_table('common_week')
        
        # Deleting model 'Room'
        db.delete_table('common_room')
        
        # Deleting model 'UserSet'
        db.delete_table('common_userset')
        
        # Deleting model 'Exam'
        db.delete_table('common_exam')
        
        # Deleting model 'Lecture'
        db.delete_table('common_lecture')
        
        # Dropping ManyToManyField 'Lecture.weeks'
        db.delete_table('common_lecture_weeks')
        
        # Dropping ManyToManyField 'Lecture.rooms'
        db.delete_table('common_lecture_rooms')
        
        # Dropping ManyToManyField 'Lecture.groups'
        db.delete_table('common_lecture_groups')
        
        # Dropping ManyToManyField 'Lecture.lecturers'
        db.delete_table('common_lecture_lecturers')
        
        # Dropping ManyToManyField 'UserSet.exclude'
        db.delete_table('common_userset_exclude')
        
        # Dropping ManyToManyField 'Course.semesters'
        db.delete_table('common_course_semesters')
        
        # Dropping ManyToManyField 'UserSet.groups'
        db.delete_table('common_userset_groups')
        
        # Deleting unique_together for [year, type] on Semester.
        db.delete_unique('common_semester', ['year', 'type'])
        
        # Deleting unique_together for [slug, course, semester] on UserSet.
        db.delete_unique('common_userset', ['slug', 'course_id', 'semester_id'])
        
    
    
    models = {
        'common.course': {
            'full_name': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '100'}),
            'points': ('django.db.models.fields.DecimalField', [], {'null': 'True', 'max_digits': '5', 'decimal_places': '2'}),
            'semesters': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['common.Semester']", 'null': 'True', 'blank': 'True'}),
            'url': ('django.db.models.fields.URLField', [], {'max_length': '200', 'blank': 'True'})
        },
        'common.deadline': {
            'date': ('django.db.models.fields.DateField', [], {'default': 'datetime.date(2009, 8, 12)'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'task': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'time': ('django.db.models.fields.TimeField', [], {'null': 'True', 'blank': 'True'}),
            'userset': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['common.UserSet']"})
        },
        'common.exam': {
            'comment': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'course': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['common.Course']"}),
            'duration': ('django.db.models.fields.PositiveSmallIntegerField', [], {'null': 'True', 'blank': 'True'}),
            'exam_date': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'exam_time': ('django.db.models.fields.TimeField', [], {'null': 'True', 'blank': 'True'}),
            'handout_date': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'handout_time': ('django.db.models.fields.TimeField', [], {'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'semester': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['common.Semester']", 'null': 'True'}),
            'type': ('django.db.models.fields.CharField', [], {'max_length': '1', 'blank': 'True'}),
            'type_name': ('django.db.models.fields.CharField', [], {'max_length': '100', 'null': 'True', 'blank': 'True'})
        },
        'common.group': {
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '100'})
        },
        'common.lecture': {
            'course': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['common.Course']"}),
            'day': ('django.db.models.fields.PositiveSmallIntegerField', [], {}),
            'end': ('django.db.models.fields.TimeField', [], {}),
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['common.Group']", 'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'lecturers': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['common.Lecturer']", 'null': 'True', 'blank': 'True'}),
            'rooms': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['common.Room']", 'null': 'True', 'blank': 'True'}),
            'semester': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['common.Semester']"}),
            'start': ('django.db.models.fields.TimeField', [], {}),
            'type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['common.Type']", 'null': 'True', 'blank': 'True'}),
            'weeks': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['common.Week']", 'null': 'True', 'blank': 'True'})
        },
        'common.lecturer': {
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '200'})
        },
        'common.room': {
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '100'})
        },
        'common.semester': {
            'Meta': {'unique_together': "[('year', 'type')]"},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'type': ('django.db.models.fields.PositiveSmallIntegerField', [], {}),
            'year': ('django.db.models.fields.PositiveSmallIntegerField', [], {})
        },
        'common.type': {
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '100'}),
            'optional': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'})
        },
        'common.userset': {
            'Meta': {'unique_together': "(('slug', 'course', 'semester'),)"},
            'added': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'course': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['common.Course']"}),
            'exclude': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['common.Lecture']", 'null': 'True', 'blank': 'True'}),
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['common.Group']", 'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '50', 'blank': 'True'}),
            'semester': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['common.Semester']"}),
            'slug': ('django.db.models.fields.SlugField', [], {'max_length': '50', 'db_index': 'True'})
        },
        'common.week': {
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'number': ('django.db.models.fields.PositiveIntegerField', [], {'unique': 'True'})
        }
    }
    
    complete_apps = ['common']
