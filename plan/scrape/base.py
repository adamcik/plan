# This file is part of the plan timetable generator, see LICENSE for details.

class Scraper(object):
    def __init__(self, semester, options):
        self.semester = semester
        self.options = options

    def fetch(self):
        raise NotImplementedError

    def run(self):
        return self.fetch()
