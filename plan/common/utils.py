import time
import logging

from django.conf import settings
from django.http import HttpResponseServerError
from django.template import Context, loader

class Timer(object):
    '''http://www.djangosnippets.org/snippets/783/ -- By Ed and Rudy Menendez'''
    def __init__(self):
        self.bot = self.last_time = time.time()

        logging.info(u'Starting timer at %s' % self.last_time)

    def tick(self, msg='Timer'):
        x = time.time()
        logging.info(u'%s: Since inception %.3f, since last call %.3f' % (msg, (x-self.bot)*1000, (x - self.last_time)*1000))
        self.last_time = x

def server_error(request, template_name='500.html'):
    """
    500 error handler.

    Templates: `500.html`
    Context: None
    """
    t = loader.get_template(template_name) # You need to create a 500.html template.
    return HttpResponseServerError(t.render(Context({'MEDIA_URL': settings.MEDIA_URL})))

def compact_sequence(sequence):
    if not sequence:
        return []

    sequence.sort()

    compact = []
    first = sequence[0]
    last = sequence[0] - 1

    for i,week in enumerate(sequence):
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
