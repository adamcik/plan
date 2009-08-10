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


from plan.settings.base import *
from plan.settings.local import *

TEST_RUNNER = 'plan.common.test_runner.test_runner_with_coverage'

COVERAGE_MODULES = (
    'plan.common.admin',
    'plan.common.cache',
    'plan.common.forms',
    'plan.common.logger',
    'plan.common.managers',
    'plan.common.middleware',
    'plan.common.models',
    'plan.common.timetable',
    'plan.common.urls',
    'plan.common.utils',
    'plan.common.views',
    'plan.scrape.db',
    'plan.scrape.studweb',
    'plan.ical.urls',
    'plan.ical.views',
    'plan.pdf.urls',
    'plan.pdf.views',
)
