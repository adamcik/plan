# This file is part of the plan timetable generator, see LICENSE for details.


from django import template
from lxml import html

register = template.Library()


@register.tag(name="nonce")
def do_nonce(parser, token):
    try:
        name, nonce = token.split_contents()
    except ValuerError:
        raise template.TemplateSyntaxError("'nonce' tag requires a single argument")

    nodelist = parser.parse(("endnonce",))
    parser.delete_first_token()
    return Nonce(nonce, nodelist)


class Nonce(template.Node):
    def __init__(self, nonce, nodelist) -> None:
        self.nonce = template.Variable(nonce)
        self.nodelist = nodelist

    def render(self, context):
        output = self.nodelist.render(context)
        nonce = self.nonce.resolve(context)

        tag = html.fragment_fromstring(output)
        if nonce:
            tag.attrib["nonce"] = nonce
        return html.tostring(tag).decode("utf-8")
