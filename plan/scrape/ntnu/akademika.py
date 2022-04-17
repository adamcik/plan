# This file is part of the plan timetable generator, see LICENSE for details.

from plan.scrape import base
from plan.scrape import fetch


def fetch_syllabus(code):
    query = {"curriculum": code.encode("utf-8")}
    root = fetch.html("https://www.akademika.no/curriculum/search", query=query)
    for e in root.cssselect(".curriculum-search-result[data-id]"):
        if not e.xpath('.//a[contains(text(),"NTNU")]'):
            continue
        url = "https://www.akademika.no/ajax/curriculum/" + e.attrib["data-id"]
        for (_, _, href, _) in fetch.html(url, verbose=True).iterlinks():
            if href.startswith("/pensum/%s-" % code.lower()):
                return "https://www.akademika.no" + href
    return ""


class Syllabus(base.SyllabusScraper):
    def scrape(self):
        for course in self.queryset():
            yield {"code": course.code, "syllabus": fetch_syllabus(course.code)}
