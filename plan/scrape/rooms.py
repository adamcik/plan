# Copyright 2008, 2009 Thomas Kongevold Adamcik

# This file is part of Plan.
#
# Plan is free software: you can redistribute it and/or modify
# it under the terms of the Affero GNU General Public License as
# published by the Free Software Foundation, either version 3 of
# the License, or (at your option) any later version.
#
# Plan is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# Affero GNU General Public License for more details.
#
# You should have received a copy of the Affero GNU General Public
# License along with Plan.  If not, see <http://www.gnu.org/licenses/>.

import logging
import re

from urllib import urlencode
from lxml.html import fromstring

from plan.common.models import Room, Course
from plan.scrape import fetch_url

logger = logging.getLogger('plan.scrape.rooms')

def update_rooms():
    room_links = {}

    for room in Room.objects.all():
        url = 'http://www.ntnu.no/kart/no_cache/soek/?%s' % \
            urlencode({'tx_indexedsearch[sword]': room.name.encode('latin1')})

        logger.info('Retrieving %s', url)

        try:
            html = fetch_url(url)
            root = fromstring(html)
        except IOError, e:
            logger.error('Loading falied')
            continue

        for a in root.cssselect('span.tx-indexedsearch-path a'):
            link = a.attrib['href']

            # FIXME blacklist check?
            if 'plantegning' in link:
                continue
            if 'ntnu.edu' in link:
                continue
            if not link.startswith('http'):
                continue

            if room not in room_links:
                room_links[room] = []

            room_links[room].append(link.rstrip('?0='))

    for room, links in room_links.items():
        choice = get_choice(room, links)

        if choice:
            room.url = 'http://www.ntnu.no/kart/' + choice
            room.save()

def get_course_codes(room):
    codes = Course.objects.filter(lecture__rooms=room)
    codes = codes.values_list('code', flat=True).distinct()
    return set([re.match(r'^([^0-9]+)[0-9]+$', c).group(1) for c in codes])

def get_choice(room, links):
    if not links:
        return ''

    if len(links) == 1:
        return links[0]

    codes = get_course_codes(room)
    print '\n%s: %s' % (room.name, ', '.join(sorted(codes)))

    for i, link in enumerate(sorted(links)):
        print '%d) %s' % (i+1, link)

    while True:
        choice = raw_input()
        if choice == '':
            return ''

        if not choice.isdigit():
            continue
        choice = int(choice)

        if choice < 1 or choice > len(links):
            continue

        break

    return links[choice-1]
