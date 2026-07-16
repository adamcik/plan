# This file is part of the plan timetable generator, see LICENSE for details.

from django.template import Context, Template


def test_nonce_is_added_to_script_tags():
    template = Template(
        """
        {% load nonce %}
        {% nonce script %}
          <script src=\"/static/app.js\"></script>
        {% endnonce %}
        """
    )

    rendered = template.render(Context({"CSP_SCRIPT_NONCE": "abc123"}))

    assert 'nonce="abc123"' in rendered
    assert 'src="/static/app.js"' in rendered


def test_nonce_is_not_added_without_context_value():
    template = Template(
        """
        {% load nonce %}
        {% nonce script %}
          <script src=\"/static/app.js\"></script>
        {% endnonce %}
        """
    )

    rendered = template.render(Context({}))

    assert 'nonce="' not in rendered


def test_nonce_is_added_to_style_tags():
    template = Template(
        """
        {% load nonce %}
        {% nonce style %}
          <style>body { color: black; }</style>
        {% endnonce %}
        """
    )

    rendered = template.render(Context({"CSP_STYLE_NONCE": "style123"}))

    assert 'nonce="style123"' in rendered
    assert "body { color: black; }" in rendered
