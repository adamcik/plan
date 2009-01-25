# encoding: utf-8

from django import forms
from django.db.models import Q
from django.template.defaultfilters import slugify

from plan.common.models import Deadline, Semester

class CourseNameForm(forms.Form):
    '''Form for changing userset names'''
    name = forms.CharField(widget=forms.TextInput(attrs={'size':8}),
                           required=False)

    def clean_name(self):
        name = self.cleaned_data['name']

        if len(name) > 40:
            name = '%s...' % name[:40].rstrip()

        return name

class GroupForm(forms.Form):
    '''Form for selecting groups for a course (has a custom init)'''
    groups = forms.MultipleChoiceField(required=False)

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
        self.fields['userset'].label_from_instance = lambda obj: obj.name or obj.course.name

        self.fields['time'].widget.attrs['size'] = 2
        self.fields['date'].widget.attrs['size'] = 7
        self.fields['task'].widget.attrs['size'] = 28

class ScheduleForm(forms.Form):
    slug = forms.CharField()
    semester = forms.ModelChoiceField(Semester.objects.all(), required=False)

    def __init__(self, *args, **kwargs):
        super(ScheduleForm, self).__init__(*args, **kwargs)

        current = Semester.current()
        semester_test = Q(year__exact=current.year, type__gte=current.type) | \
            Q(year__gte=current.year)

        self.fields['semester'].queryset = self.fields['semester']. \
                queryset.filter(semester_test)

        if len(self.fields['semester'].queryset) == 1:
            self.fields['semester'].widget = forms.HiddenInput()

    def clean_slug(self):
        slug = self.cleaned_data['slug'].lower()

        # FIXME remove this before next semester...
        return slugify(slug)

        for letters in [(u'æ', u'ae'), (u'ø', u'o'), (u'å', u'aa')]:
            slug = slug.replace(*letters)

        return slugify(slug)
