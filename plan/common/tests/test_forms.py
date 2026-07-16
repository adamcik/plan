from plan.common.forms import GroupForm


def test_group_choices_allow_missing_group_names():
    form = GroupForm(
        [
            ("other", None),
            ("group-10", "Group 10"),
            ("group-2", "Group 2"),
        ]
    )

    assert list(form.fields["groups"].choices) == [
        ("other", None),
        ("group-2", "Group 2"),
        ("group-10", "Group 10"),
    ]
