from django import forms

from plan.common.models import *

class CourseForm(forms.Form):
    courses = forms.models.ModelMultipleChoiceField(Course.objects.all())

class LectureForm(forms.models.ModelForm):
    class Meta:
        model = Lecture

class GroupForm(forms.Form):
    groups = forms.models.ModelMultipleChoiceField(Group.objects.all(), required=False)

    def __init__(self, queryset, *args, **kwargs):
        super(GroupForm, self).__init__(*args, **kwargs)

        self.fields['groups'].queryset = queryset
        self.fields['groups'].widget.attrs['size'] = 5
