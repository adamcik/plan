from django import template

register = template.Library()

@register.tag(name='color')
def do_color(parser, token):
    try:
        tag_name, id = token.split_contents()
    except ValueError:
        raise template.TemplateSyntaxError, "%r tag requires a single argument" % token.contents.split()[0]
    if id[0] == id[-1] and id[0] in ('"', "'"):
        raise template.TemplateSyntaxError, "%r tag's argument should not be in quotes" % tag_name
    return ColorNode(id)

class ColorNode(template.Node):
    def __init__(self, id):
        self.id = id
    def render(self, context):
        try:
            id = template.Variable(self.id).resolve(context)
            return template.Variable('color_map').resolve(context)[id]
        except template.VariableDoesNotExist:
            return ''
