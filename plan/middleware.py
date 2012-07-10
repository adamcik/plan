# This file is part of the plan timetable generator, see LICENSE for details.

from django import http
from django import shortcuts
from django.conf import settings
from django.core import urlresolvers
from django.utils import translation

from plan.common.models import Semester


class LocaleMiddleware(object):
    def __init__(self):
        self.languages = {}  # Localised semester type -> lang
        self.values = {}     # Localised semester type -> db value

        for lang, name in settings.LANGUAGES:
            with translation.override(lang):
                for value, slug in Semester.SEMESTER_SLUG:
                    self.languages[unicode(slug)] = lang
                    self.values[unicode(slug)] = value

    def process_view(self, request, view, args, kwargs):
        # Default to guessing base on accept when we don't know.
        if 'semester_type' not in kwargs:
            translation.activate(
                translation.get_language_from_request(request))
        else:
            # Convert localised semester type to lang and db value.
            try:
                semester = kwargs['semester_type']
                translation.activate(self.languages[semester])
                kwargs['semester_type'] = self.values[semester]
            except KeyError:
                raise http.Http404

            # Support ?en etc, if this is present we activate the lang and
            # resolve the current url to get its name and reverse it with a
            # localised semester type.
            if request.META['QUERY_STRING'] in dict(settings.LANGUAGES):
                translation.activate(request.META['QUERY_STRING'])
                match = urlresolvers.resolve(request.path_info)
                kwargs['semester_type'] = dict(Semester.SEMESTER_SLUG)[kwargs['semester_type']]
                return shortcuts.redirect(match.url_name, *args, **kwargs)

        try:
            return view(request, *args, **kwargs)
        finally:
            translation.deactivate()
