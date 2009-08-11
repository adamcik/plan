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

from datetime import datetime, timedelta

from django import forms
from django.db.models import Q

from plan.common.templatetags.slugify import slugify
from plan.common.models import Deadline, Semester

now = datetime.now # To allow for overriding of now in test

class CourseAliasForm(forms.Form):
    '''Form for changing userset names'''
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

        self.fields['groups'].choices = choices
        self.fields['groups'].widget.attrs['size'] = 5

class DeadlineForm(forms.models.ModelForm):
    '''Form for adding deadlines'''

    class Meta:
        model = Deadline

    def __init__(self, queryset, *args, **kwargs):
        super(DeadlineForm, self).__init__(*args, **kwargs)

        self.fields['userset'].queryset = queryset
        self.fields['userset'].widget.attrs['style'] = 'width: 7em'
        self.fields['userset'].label_from_instance = lambda obj: obj.alias or obj.course.code


        self.fields['date'].initial = now().date()+timedelta(days=7)
        self.fields['time'].input_formats = ['%H:%M', '%H.%M']

        self.fields['time'].widget.attrs['size'] = 2
        self.fields['date'].widget.attrs['size'] = 7
        self.fields['task'].widget.attrs['size'] = 20

class ScheduleForm(forms.Form):
    slug = forms.CharField()
    semester = forms.ModelChoiceField(Semester.objects.all(), empty_label=None)

    def __init__(self, *args, **kwargs):
        '''Display form for choosing schedule. If only one semester is
           available hide to field.'''
        qs = kwargs.pop('queryset', None)

        super(ScheduleForm, self).__init__(*args, **kwargs)

        current = Semester.current()

        semester_test = Q(year__exact=current.year, type__gte=current.type) | \
            Q(year__gte=current.year)

        if not qs:
            qs = self.fields['semester'].queryset.filter(semester_test)

        if len(qs) == 1:
            self.fields['semester'].widget = forms.HiddenInput()

        self.fields['semester'].queryset = qs

        self.fields['slug'].widget.attrs['size'] = 12
        self.fields['slug'].widget.attrs['id'] = 's'

    def clean_slug(self):
        slug = slugify(self.cleaned_data['slug'])

        if not slug:
            raise forms.ValidationError('Invalid value.')

        return slug
