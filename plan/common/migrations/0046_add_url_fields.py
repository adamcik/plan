# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Adding field 'Group.url'
        db.add_column('common_group', 'url', self.gf('django.db.models.fields.URLField')(default='', max_length=200), keep_default=False)

        # Adding field 'Exam.url'
        db.add_column('common_exam', 'url', self.gf('django.db.models.fields.URLField')(default='', max_length=200), keep_default=False)


    def backwards(self, orm):
        
        # Deleting field 'Group.url'
        db.delete_column('common_group', 'url')

        # Deleting field 'Exam.url'
        db.delete_column('common_exam', 'url')


    models = {
        'common.course': {
            'Meta': {'unique_together': "[('code', 'semester', 'version')]", 'object_name': 'Course'},
            'code': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.TextField', [], {}),
            'points': ('django.db.models.fields.DecimalField', [], {'null': 'True', 'max_digits': '5', 'decimal_places': '2'}),
            'semester': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['common.Semester']"}),
            'syllabus': ('django.db.models.fields.URLField', [], {'max_length': '200'}),
            'url': ('django.db.models.fields.URLField', [], {'max_length': '200'}),
            'version': ('django.db.models.fields.CharField', [], {'max_length': '20', 'null': 'True'})
        },
        'common.deadline': {
            'Meta': {'object_name': 'Deadline'},
            'date': ('django.db.models.fields.DateField', [], {}),
            'done': ('django.db.models.fields.DateTimeField', [], {'null': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'subscription': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['common.Subscription']"}),
            'task': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'time': ('django.db.models.fields.TimeField', [], {'null': 'True'})
        },
        'common.exam': {
            'Meta': {'object_name': 'Exam'},
            'combination': ('django.db.models.fields.CharField', [], {'max_length': '50', 'null': 'True'}),
            'course': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['common.Course']"}),
            'duration': ('django.db.models.fields.DecimalField', [], {'null': 'True', 'max_digits': '5', 'decimal_places': '2'}),
            'exam_date': ('django.db.models.fields.DateField', [], {'null': 'True'}),
            'exam_time': ('django.db.models.fields.TimeField', [], {'null': 'True'}),
            'handout_date': ('django.db.models.fields.DateField', [], {'null': 'True'}),
            'handout_time': ('django.db.models.fields.TimeField', [], {'null': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['common.ExamType']", 'null': 'True'}),
            'url': ('django.db.models.fields.URLField', [], {'default': "''", 'max_length': '200'})
        },
        'common.examtype': {
            'Meta': {'object_name': 'ExamType'},
            'code': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '20'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100', 'null': 'True'})
        },
        'common.group': {
            'Meta': {'object_name': 'Group'},
            'code': ('django.db.models.fields.CharField', [], {'max_length': '20', 'unique': 'True', 'null': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100', 'null': 'True'}),
            'url': ('django.db.models.fields.URLField', [], {'default': "''", 'max_length': '200'})
        },
        'common.lecture': {
            'Meta': {'object_name': 'Lecture'},
            'course': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['common.Course']"}),
            'day': ('django.db.models.fields.PositiveSmallIntegerField', [], {}),
            'end': ('django.db.models.fields.TimeField', [], {}),
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['common.Group']", 'null': 'True', 'symmetrical': 'False'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'lecturers': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['common.Lecturer']", 'null': 'True', 'symmetrical': 'False'}),
            'rooms': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['common.Room']", 'null': 'True', 'symmetrical': 'False'}),
            'start': ('django.db.models.fields.TimeField', [], {}),
            'type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['common.LectureType']", 'null': 'True'})
        },
        'common.lecturer': {
            'Meta': {'object_name': 'Lecturer'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '200'})
        },
        'common.lecturetype': {
            'Meta': {'object_name': 'LectureType'},
            'code': ('django.db.models.fields.CharField', [], {'max_length': '20', 'unique': 'True', 'null': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '100'}),
            'optional': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        'common.room': {
            'Meta': {'object_name': 'Room'},
            'code': ('django.db.models.fields.CharField', [], {'max_length': '20', 'unique': 'True', 'null': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '100'}),
            'url': ('django.db.models.fields.URLField', [], {'default': "''", 'max_length': '200'})
        },
        'common.semester': {
            'Meta': {'unique_together': "[('year', 'type')]", 'object_name': 'Semester'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'type': ('django.db.models.fields.CharField', [], {'max_length': '10'}),
            'year': ('django.db.models.fields.PositiveSmallIntegerField', [], {})
        },
        'common.student': {
            'Meta': {'object_name': 'Student'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'show_deadlines': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'slug': ('django.db.models.fields.SlugField', [], {'unique': 'True', 'max_length': '50', 'db_index': 'True'})
        },
        'common.subscription': {
            'Meta': {'unique_together': "(('student', 'course'),)", 'object_name': 'Subscription'},
            'added': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'alias': ('django.db.models.fields.CharField', [], {'max_length': '50', 'blank': 'True'}),
            'course': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['common.Course']"}),
            'exclude': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "'excluded_from'", 'null': 'True', 'to': "orm['common.Lecture']"}),
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['common.Group']", 'null': 'True', 'symmetrical': 'False'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'student': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['common.Student']"})
        },
        'common.week': {
            'Meta': {'unique_together': "[('lecture', 'number')]", 'object_name': 'Week'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'lecture': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'weeks'", 'to': "orm['common.Lecture']"}),
            'number': ('django.db.models.fields.PositiveIntegerField', [], {})
        }
    }

    complete_apps = ['common']
