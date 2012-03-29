# Copyright 2008, 2009 Thomas Kongevold Adamcik
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

from django.conf.urls.defaults import *
from django.conf import settings

handler500 = 'plan.common.utils.server_error'

if settings.DEBUG:
    urlpatterns = patterns('',
        url(r'^500/$', 'django.views.generic.simple.direct_to_template', {'template': '500.html'}),
        url(r'^404/$', 'django.views.generic.simple.direct_to_template', {'template': '404.html'}),
    )
else:
    urlpatterns = patterns('')

urlpatterns += patterns('',
    (r'^i18n/', include('django.conf.urls.i18n')),

    (r'^', include('plan.common.urls')),
    (r'^', include('plan.ical.urls')),
    (r'^', include('plan.pdf.urls')),

)

