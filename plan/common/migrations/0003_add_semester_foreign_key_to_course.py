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

        # Adding field 'Course.semester'
        db.add_column('common_course', 'semester', orm['common.course:semester'])



    def backwards(self, orm):

        # Deleting field 'Course.semester'
        db.delete_column('common_course', 'semester_id')



    models = {
        'common.course': {
            'full_name': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '100'}),
            'points': ('django.db.models.fields.DecimalField', [], {'null': 'True', 'max_digits': '5', 'decimal_places': '2'}),
            'semester': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'foo'", 'null': 'True', 'to': "orm['common.Semester']"}),
            'semesters': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['common.Semester']", 'null': 'True', 'blank': 'True'}),
            'url': ('django.db.models.fields.URLField', [], {'max_length': '200', 'blank': 'True'}),
            'version': ('django.db.models.fields.CharField', [], {'max_length': '20', 'null': 'True', 'blank': 'True'})
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
