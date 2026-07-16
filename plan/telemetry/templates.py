"""OpenTelemetry instrumentation for Django template rendering."""

from opentelemetry import trace

_tracer = trace.get_tracer(__name__)
_instrumented = False


def instrument_templates() -> None:
    """Create a span for each top-level Django template render."""
    global _instrumented
    if _instrumented:
        return

    from django.template.backends.django import Template

    original_render = Template.render

    def render(self, context=None, request=None):
        name = self.template.name or "<string>"
        with _tracer.start_as_current_span(f"TEMPLATE {name}") as span:
            span.set_attribute("django.template.name", name)
            return original_render(self, context, request)

    Template.render = render
    _instrumented = True
