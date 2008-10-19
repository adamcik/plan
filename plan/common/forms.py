from django import forms

from plan.common.models import Deadline, Group

class CourseNameForm(forms.Form):
    '''Form for changing userset names'''
    name = forms.CharField(widget=forms.TextInput(attrs={'size':8}),
                           required=False)

class GroupForm(forms.Form):
    '''Form for selecting groups for a course (has a custom init)'''
    groups = forms.models.ModelMultipleChoiceField(Group.objects.all(),
                                                   required=False)

    def __init__(self, queryset, *args, **kwargs):
        super(GroupForm, self).__init__(*args, **kwargs)

        self.fields['groups'].queryset = queryset
        self.fields['groups'].widget.attrs['size'] = 5

class DeadlineForm(forms.models.ModelForm):
    '''Form for adding deadlines'''
    class Meta:
        model = Deadline

    def __init__(self, queryset, *args, **kwargs):
        super(DeadlineForm, self).__init__(*args, **kwargs)

        self.fields['userset'].queryset = queryset
        self.fields['userset'].widget.attrs['style'] = 'width: 7em'
        self.fields['time'].widget.attrs['size'] = 2
        self.fields['date'].widget.attrs['size'] = 7
        self.fields['task'].widget.attrs['size'] = 28
