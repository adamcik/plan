# This file is part of the plan timetable generator, see LICENSE for details.

from django.template import Context, Template
from django.test import SimpleTestCase


class NonceTemplateTagTestCase(SimpleTestCase):
    def test_nonce_is_added_to_script_tags(self):
        template = Template(
            """
            {% load nonce %}
            {% nonce script %}
              <script src=\"/static/app.js\"></script>
            {% endnonce %}
            """
        )

        rendered = template.render(Context({"CSP_SCRIPT_NONCE": "abc123"}))

        self.assertIn('nonce="abc123"', rendered)
        self.assertIn('src="/static/app.js"', rendered)

    def test_nonce_is_not_added_without_context_value(self):
        template = Template(
            """
            {% load nonce %}
            {% nonce script %}
              <script src=\"/static/app.js\"></script>
            {% endnonce %}
            """
        )

        rendered = template.render(Context({}))

        self.assertNotIn('nonce="', rendered)

    def test_nonce_is_added_to_style_tags(self):
        template = Template(
            """
            {% load nonce %}
            {% nonce style %}
              <style>body { color: black; }</style>
            {% endnonce %}
            """
        )

        rendered = template.render(Context({"CSP_STYLE_NONCE": "style123"}))

        self.assertIn('nonce="style123"', rendered)
        self.assertIn("body { color: black; }", rendered)
