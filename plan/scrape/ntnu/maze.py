# This file is part of the plan timetable generator, see LICENSE for details.

from __future__ import absolute_import
import re

from plan.scrape import base
from plan.scrape import fetch


def normalize(identifier):
    return re.sub(r'[.-]', '', identifier).upper()


def fetch_pois(tag):
    campuses = fetch.json('http://use.mazemap.com/api/campuscollections/?tag=%s' % tag)
    base_url = 'http://api.mazemap.com/api/pois/?campusid=%s'

    pois = {}
    for campus in campuses['children']:
        data = fetch.json(base_url % campus['campusId'])
        for p in data.get('pois', []):
            if p['identifier'] and not p['deleted']:
                pois[normalize(p['identifier'])] = p
    return pois


class Rooms(base.RoomScraper):
    def scrape(self):
        pois = fetch_pois('ntnu-trondheim')
        base_url = 'http://use.mazemap.com/?campusid=%s&desttype=identifier&dest=%s'

        for room in self.queryset().filter(code__isnull=False):
            poi = pois.get(normalize(room.code))

            if not poi:
                continue

            yield {'code': room.code,
                   'name': room.name,
                   'url': base_url % (poi['campusId'], poi['identifier'])}
