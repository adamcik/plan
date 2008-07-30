import time
import logging
class Timer(object):
    '''http://www.djangosnippets.org/snippets/783/ -- By Ed and Rudy Menendez'''
    def __init__(self):
        self.bot = self.last_time = time.time()

        logging.info(u'Starting timer at %s' % self.last_time)

    def tick(self, msg='Timer'):
        x = time.time()
        logging.info(u'%s: Since inception %.3f, since last call %.3f' % (msg, (x-self.bot)*1000, (x - self.last_time)*1000))
        self.last_time = x
