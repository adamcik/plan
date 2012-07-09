# This file is part of the plan timetable generator, see LICENSE for details.

import logging
import lxml.html
import re
import urllib

from plan.common.models import Room, Course
from plan.scrape import utils

logger = logging.getLogger('plan.scrape.rooms')

def update_rooms():
    room_links = {}

    for room in Room.objects.all():
        query = {'tx_indexedsearch[sword]': room.name.encode('latin1')}
        url = 'http://www.ntnu.no/kart/no_cache/soek/?{0}'.format(
            urllib.urlencode(query))

        logger.info('Retrieving %s', url)
        try:
            root = lxml.html.fromstring(utils.cached_urlopen(url))
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
    return codes.values_list('code', flat=True).distinct()

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
