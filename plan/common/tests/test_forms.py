from django.test import SimpleTestCase

from plan.common.forms import GroupForm


class GroupFormTest(SimpleTestCase):
    def test_group_choices_allow_missing_group_names(self):
        form = GroupForm(
            [
                ("other", None),
                ("group-10", "Group 10"),
                ("group-2", "Group 2"),
            ]
        )

        self.assertEqual(
            list(form.fields["groups"].choices),
            [("other", None), ("group-2", "Group 2"), ("group-10", "Group 10")],
        )
