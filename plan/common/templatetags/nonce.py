# This file is part of the plan timetable generator, see LICENSE for details.


from lxml import html
from lxml.etree import ParserError

from django import template

register = template.Library()


@register.tag(name="nonce")
def do_nonce(parser, token):
    parts = token.split_contents()
    if len(parts) != 2:
        raise template.TemplateSyntaxError(
            "'nonce' tag usage: {% nonce script|style %}"
        )

    _, target = parts

    target = target.lower()
    if target not in ("script", "style"):
        raise template.TemplateSyntaxError(
            "'nonce' tag type must be 'script' or 'style'"
        )

    nodelist = parser.parse(("endnonce",))
    parser.delete_first_token()
    return Nonce(target, nodelist)


class Nonce(template.Node):
    def __init__(self, target, nodelist) -> None:
        self.target = target
        self.nodelist = nodelist

    def render(self, context):
        output = self.nodelist.render(context)
        if not output.strip():
            return output

        nonce = context.get(f"CSP_{self.target.upper()}_NONCE")
        if not nonce:
            return output

        try:
            tags = html.fragments_fromstring(output)
        except ParserError:
            return output

        rendered = []
        for tag in tags:
            if isinstance(tag, str):
                rendered.append(tag)
                continue

            name = str(getattr(tag, "tag", "")).lower()
            if name == self.target:
                tag.attrib["nonce"] = nonce
            rendered.append(html.tostring(tag, encoding="unicode"))

        return "".join(rendered)
