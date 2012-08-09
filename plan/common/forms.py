# This file is part of the plan timetable generator, see LICENSE for details.

import datetime

from django import forms
from django.db import models

from plan.common.models import Deadline, Semester

from plan.common.templatetags import slugify

now = datetime.datetime.now # To allow for overriding of now in test


class CourseAliasForm(forms.Form):
    '''Form for changing subscription names'''
    alias = forms.CharField(widget=forms.TextInput(attrs={'size':8}),
                           required=False)

    def clean_alias(self):
        alias = self.cleaned_data['alias'].strip()

        if len(alias) > 40:
            alias = '%s...' % alias[:40]

        return alias


class GroupForm(forms.Form):
    '''Form for selecting groups for a course'''
    groups = forms.MultipleChoiceField(required=False, widget=forms.CheckboxSelectMultiple)

    def __init__(self, choices, *args, **kwargs):
        super(GroupForm, self).__init__(*args, **kwargs)

        i = 0
        initial_groups = self.initial.get('groups', [])

        for id, name in choices:
            if id in initial_groups:
                choices.remove((id, name))
                choices.insert(i, (id, name))

                i += 1

        self.fields['groups'].choices = choices
        self.fields['groups'].widget.attrs['size'] = 5


class DeadlineForm(forms.models.ModelForm):
    '''Form for adding deadlines'''

    class Meta:
        model = Deadline

    def __init__(self, queryset, *args, **kwargs):
        super(DeadlineForm, self).__init__(*args, **kwargs)

        self.fields['subscription'].queryset = queryset
        self.fields['subscription'].widget.attrs['style'] = 'width: 7em'
        self.fields['subscription'].label_from_instance = lambda obj: obj.alias or obj.course.code

        self.fields['date'].initial = now().date()+datetime.timedelta(days=7)
        self.fields['time'].input_formats = ['%H:%M', '%H.%M']
        self.fields['time'].required = False

        self.fields['time'].widget.attrs['size'] = 2
        self.fields['date'].widget.attrs['size'] = 7
        self.fields['task'].widget.attrs['size'] = 20


class ScheduleForm(forms.Form):
    slug = forms.CharField(max_length=50)

    def __init__(self, *args, **kwargs):
        super(ScheduleForm, self).__init__(*args, **kwargs)
        self.fields['slug'].widget.attrs['size'] = 12
        self.fields['slug'].widget.attrs['id'] = 's'

    def clean_slug(self):
        slug = slugify.slugify(self.cleaned_data['slug'])
        if not slug:
            raise forms.ValidationError('Invalid value.')
        return slug
