from django import forms

from plan.common.models import *

class CourseForm(forms.Form):
    courses = forms.models.ModelMultipleChoiceField(Course.objects.all())

class LectureForm(forms.models.ModelForm):
    class Meta:
        model = Lecture
