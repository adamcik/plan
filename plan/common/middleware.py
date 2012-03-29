# Copyright 2008, 2009 Thomas Kongevold Adamcik
# 2009 IME Faculty Norwegian University of Science and Technology

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


class PlainContentMiddleware(object):
    def __init__(self):
        self.logger = logging.getLogger('plan.middleware.plain')

    def process_response(self, request, response):
        if 'plain' in request.GET:
            self.logger.debug('Forcing text/plain')

            if 'Filename' in response:
                del response['Filename']
            if 'Content-Disposition' in response:
                del response['Content-Disposition']

            response['Content-Type'] = 'text/plain; charset=utf-8'

        return response
