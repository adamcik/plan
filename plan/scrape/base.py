# This file is part of the plan timetable generator, see LICENSE for details.

class Scraper(object):
    def __init__(self, semester, options):
        self.semester = semester
        self.options = options

    def run(self):
        raise NotImplementedError
