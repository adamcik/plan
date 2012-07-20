# This file is part of the plan timetable generator, see LICENSE for details.

import re

from django import http
from django import shortcuts
from django.conf import settings
from django.core import urlresolvers
from django.utils import cache
from django.utils import translation
from django.utils.translation import trans_real as trans_internals

from plan.common.models import Semester

RE_WHITESPACE = re.compile(r'(\s\s+|\n)')


class HtmlMinifyMiddleware(object):
    def process_response(self, request, response):
        if response.status_code == 200 and 'text/html' in response['Content-Type']:
            response.content = RE_WHITESPACE.sub(' ', response.content)
        return response


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
        if 'semester_type' not in kwargs:
            language = self.guess_language_from_accept_header(request)
        else:
            # Use semester type to set language, and convert localised value to
            # db value.
            try:
                semester = kwargs['semester_type']
                language = self.languages[semester]
                kwargs['semester_type'] = self.values[semester]
            except KeyError:
                raise http.Http404

            if request.META['QUERY_STRING'] in dict(settings.LANGUAGES):
                return self.rederict_to_new_language(request, args, kwargs)

        with translation.override(language, deactivate=True):
            response = view(request, *args, **kwargs)
            response['Content-Language'] = language

        if 'semester_type' not in kwargs:
            # Only set vary header when we had to guess.
            cache.patch_vary_headers(response, ('Accept-Language',))

        return response

    def guess_language_from_accept_header(self, request):
        supported = dict(settings.LANGUAGES)
        accept = request.META.get('HTTP_ACCEPT_LANGUAGE', '')

        for lang, unused in trans_internals.parse_accept_lang_header(accept):
            if lang == '*':
                break
            lang = lang.split('-')[0].lower()
            if settings.LANGUAGE_FALLBACK.get(lang, lang) in supported:
                return lang
        return settings.LANGUAGE_CODE

    def rederict_to_new_language(self, request, args, kwargs):
        # Support ?lang etc, if this is present we activate the lang and
        # resolve the current url to get its name and reverse it with a
        # localised semester type.
        with translation.override(request.META['QUERY_STRING'], deactivate=True):
            match = urlresolvers.resolve(request.path_info)
            kwargs['semester_type'] = dict(Semester.SEMESTER_SLUG)[kwargs['semester_type']]
            return shortcuts.redirect(match.url_name, *args, **kwargs)
