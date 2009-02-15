import re

from django import template

register = template.Library()

@register.tag(name='stripspace')
def do_stripspace(parser, token):
    nodelist = parser.parse(('endstripspace',))
    parser.delete_first_token()
    return StripNode(nodelist)

class StripNode(template.Node):
    def __init__(self, nodelist):
        self.nodelist = nodelist

    def render(self, context):
        output = self.nodelist.render(context)
        return re.sub('\s+', ' ', output).strip()

@register.tag(name='stripblank')
def do_stripblank(parser, token):
    nodelist = parser.parse(('endstripblank',))
    parser.delete_first_token()
    return BlankNode(nodelist)

class BlankNode(template.Node):
    def __init__(self, nodelist):
        self.nodelist = nodelist

    def render(self, context):
        return '\n'.join([line for line in self.nodelist.render(context).split('\n') if line.strip()])
