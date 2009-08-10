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

import coverage

from django.test.simple import run_tests as django_test_runner
from django.conf import settings

def test_runner_with_coverage(test_labels, verbosity=1, interactive=True,
    extra_tests=[]):
    """Custom test runner. Follows the django.test.simple.run_tests()
    interface."""

    # Start code coverage before anything else if necessary
    if hasattr(settings, 'COVERAGE_MODULES'):
        coverage.use_cache(0) # Do not cache any of the coverage.py stuff
        coverage.start()

    test_results = django_test_runner(test_labels, verbosity, interactive,
                                      extra_tests)

    if not hasattr(settings, 'COVERAGE_MODULES'):
        return test_results

    # Stop code coverage after tests have completed
    coverage.stop()

    # Report code coverage metrics
    coverage_modules = []
    for module in settings.COVERAGE_MODULES:
        coverage_modules.append(__import__(module, globals(), locals(), ['']))

    print ''
    print '======================================================================'
    print ' Unit Test Code Coverage Results'
    print '----------------------------------------------------------------------'

    coverage.report(coverage_modules, show_missing=1)

    print '----------------------------------------------------------------------'

    return test_results
