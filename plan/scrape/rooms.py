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

from urllib import URLopener, urlencode
from BeautifulSoup import BeautifulSoup

from plan.common.models import Room

logger = logging.getLogger('plan.scrape.rooms')

def update_rooms():
    opener = URLopener()
    opener.addheader('Accept', '*/*')

    rooms = list(Room.objects.all())

    for i, room in enumerate(rooms):
        url = 'http://www.ntnu.no/ntnukart/undervisningsrom/sokeresultat.php?%s' % \
            urlencode({'soketekst': room.name.encode('latin1')})

        logger.info('Retrieving %s', url)

        try:
            html = ''.join(opener.open(url).readlines())
        except IOError, e:
            logger.error('Loading falied')
            continue

        soup = BeautifulSoup(html)

        hovedramme = soup.findAll('div', {'class': 'hovedramme'})[0]

        links = []

        for link in hovedramme.findAll('a'):
            if link.parent.name == 'h2':
                links.append([link.contents[0], 'http://www.ntnu.no/ntnukart/undervisningsrom/' + link['href']])

            link.extract()

        del hovedramme
        del soup

        if len(links) == 1:
            logger.info('Setting url for %s to %s', room, links[0][0])

            room.url = links[0][1]
            room.save()
        else:
            logger.warning('Skipping %s', room)
