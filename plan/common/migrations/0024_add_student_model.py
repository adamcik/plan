# Copyright 2009 Thomas Kongevold Adamcik
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

        # Adding model 'Student'
        db.create_table('common_student', (
            ('id', orm['common.student:id']),
            ('slug', orm['common.student:slug']),
        ))
        db.send_create_signal('common', ['Student'])

        # Adding field 'UserSet.student'
        db.add_column('common_userset', 'student', orm['common.userset:student'])



    def backwards(self, orm):

        # Deleting model 'Student'
        db.delete_table('common_student')

        # Deleting field 'UserSet.student'
        db.delete_column('common_userset', 'student_id')



    models = {
        'common.course': {
            'code': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'points': ('django.db.models.fields.DecimalField', [], {'null': 'True', 'max_digits': '5', 'decimal_places': '2', 'blank': 'True'}),
            'semester': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['common.Semester']"}),
            'url': ('django.db.models.fields.URLField', [], {'max_length': '200', 'blank': 'True'}),
            'version': ('django.db.models.fields.CharField', [], {'max_length': '20', 'null': 'True', 'blank': 'True'})
        },
        'common.deadline': {
            'date': ('django.db.models.fields.DateField', [], {'default': 'datetime.date(2009, 8, 17)'}),
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
            'type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['common.ExamType']", 'null': 'True', 'blank': 'True'})
        },
        'common.examtype': {
            'code': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '20'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100', 'null': 'True', 'blank': 'True'})
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
            'start': ('django.db.models.fields.TimeField', [], {}),
            'type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['common.LectureType']", 'null': 'True', 'blank': 'True'})
        },
        'common.lecturer': {
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '200'})
        },
        'common.lecturetype': {
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '100'}),
            'optional': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'})
        },
        'common.room': {
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '100'})
        },
        'common.semester': {
            'Meta': {'unique_together': "[('year', 'type')]"},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'type': ('django.db.models.fields.CharField', [], {'max_length': '10'}),
            'year': ('django.db.models.fields.PositiveSmallIntegerField', [], {})
        },
        'common.student': {
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'slug': ('django.db.models.fields.SlugField', [], {'max_length': '50', 'db_index': 'True'})
        },
        'common.userset': {
            'Meta': {'unique_together': "(('slug', 'course'),)"},
            'added': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'course': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['common.Course']"}),
            'exclude': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['common.Lecture']", 'null': 'True', 'blank': 'True'}),
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['common.Group']", 'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '50', 'blank': 'True'}),
            'slug': ('django.db.models.fields.SlugField', [], {'max_length': '50', 'db_index': 'True'}),
            'student': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['common.Student']", 'null': 'True'})
        },
        'common.week': {
            'Meta': {'unique_together': "[('lecture', 'number')]"},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'lecture': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['common.Lecture']"}),
            'number': ('django.db.models.fields.PositiveIntegerField', [], {})
        }
    }

    complete_apps = ['common']
