from django.conf import settings
from django.http import HttpResponseServerError
from django.template import Context, loader

def server_error(request, template_name='500.html'):
    """
    500 error handler.

    Templates: `500.html`
    Context: None
    """
    # You need to create a 500.html template.
    t = loader.get_template(template_name)

    context = Context({'MEDIA_URL': settings.MEDIA_URL})

    return HttpResponseServerError(t.render(context))

def compact_sequence(sequence):
    '''Nice little function that replaces sucessive ints n, ..., m  with n-m'''
    if not sequence:
        return []

    sequence.sort()

    compact = []
    first = sequence[0]
    last = sequence[0] - 1

    for week in sequence:
        if last == week - 1:
            last = week
        else:
            if first != last:
                compact.append('%d-%d' % (first, last))
            else:
                compact.append(first)

            first = week
            last = week

    if first != last:
        compact.append('%d-%d' % (first, last))
    else:
        compact.append(first)

    return compact

class ColorMap(dict):
    """Magic dict that assigns colors"""

    # Colors from www.ColorBrewer.org by Cynthia A. Brewer, Geography,
    # Pennsylvania State University.
    # http://www.personal.psu.edu/cab38/ColorBrewer/ColorBrewer_updates.html

    colors = [
        '#B3E2CD',
        '#FDCDAC',
        '#CBD5E8',
        '#F4CAE4',
        '#E6F5C9',
        '#FFF2AE',
        '#F1E2CC',
        '#CCCCCC',
    ]

    def __init__(self, index=0, max=settings.MAX_COLORS, hex=False):
        self.index = index
        self.max = max
        self.hex = hex

    def __getitem__(self, k):
        # Remember to use super to prevent inf loop
        if k is None:
            return ''

        if k in self:
            return super(ColorMap, self).__getitem__(k)
        else:
            self.index += 1
            if self.hex:
                self[k] = self.colors[self.index % self.max]
            else:
                self[k] = 'color%d' % (self.index % self.max)
            return super(ColorMap, self).__getitem__(k)
