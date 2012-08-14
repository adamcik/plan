# This file is part of the plan timetable generator, see LICENSE for details.

import re

from plan.scrape import base
from plan.scrape import fetch


class Syllabus(base.SyllabysScraper):
    def scrape(self):
        return fetch_syllabus('Norges teknisk-naturvitenskapelige universitet')


def fetch_syllabus(name_re):
    university = fetch_university(name_re)
    if not university:
        return

    for study in fetch_studies(university):
        for semester in fetch_semesters(university, study):
            for course, pack in fetch_packs(university, study, semester):
                url = fetch_node(pack)
                if url:
                    yield {'code': course, 'syllabus': url}


def fetch_university(name_re):
    root = fetch.html('http://www.akademika.no/pensum', cache=False)
    if root is None:
        return
    for option in root.cssselect('select[name="select_university"] option'):
        if re.search(name_re, option.text):
            return option.attrib['value']
    return None


def fetch_params(field, **kwargs):
    data = fetch.json('http://www.akademika.no/pensumlister/load', query=kwargs)
    for value in data.get(field, {}):
        if value == '0':
            continue
        yield value


def fetch_studies(university):
    return fetch_params('studies', university=university)


def fetch_semesters(university, study):
    return fetch_params('semesters', university=university, study=study)


def fetch_packs(university, study, semester):
    root = fetch.html('http://www.akademika.no/pensumlister/load_products',
                      query={'university': university,
                             'study': study,
                             'semester': semester})
    if root is None:
        return

    for link in root.cssselect('.packlink'):
        course = link.text.split(' ')[0]
        if course.endswith('NTNU'):
            course = course[:-len('NTNU')]
        yield course, link.attrib['rel']


def fetch_node(pack):
    root = fetch.html(
        'http://www.akademika.no/pensumlister/load_products2/%s' % pack)
    if root is None:
        return

    node = root.cssselect('[id*="node-"]')
    if not node:
        return
    node = node[0].attrib['id'].split('-')[1]
    if node:
        return 'http://www.akademika.no/node/%s' % node
