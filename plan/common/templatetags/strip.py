import re

from django import template

register = template.Library()

@register.tag(name='stripspace')
def do_stripspace(parser, token):
    nodelist = parser.parse(('endstripspace',))
    parser.delete_first_token()
    return StripNode(nodelist)

class StripNode(template.Node):
    regexp = re.compile('\s+')

    def __init__(self, nodelist):
        self.nodelist = nodelist

    def render(self, context):
        output = self.nodelist.render(context)
        return re.sub(self.regexp, ' ', output).strip()
