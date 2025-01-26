# This file is part of the plan timetable generator, see LICENSE for details.

import secrets
import re

from django import http, shortcuts, urls
from django.conf import settings
from django.utils import cache, translation
from django.utils import http as http_utils
from django.utils.deprecation import MiddlewareMixin
from django.utils.translation import trans_real as trans_internals

from plan.common.models import Semester

RE_WHITESPACE = re.compile(rb"(\s\s+|\n)")


class HtmlMinifyMiddleware(MiddlewareMixin):
    def should_minify(self, response):
        return (
            settings.COMPRESS_ENABLED
            and response.status_code == 200
            and "text/html" in response["Content-Type"]
        )

    def process_response(self, request, response):
        if self.should_minify(response):
            response.content = RE_WHITESPACE.sub(b" ", response.content)
        return response


class CspMiddleware(MiddlewareMixin):
    def process_request(self, request):
        request._csp_nonce = secrets.token_urlsafe(16)

    def process_response(self, request, response):
        if response.status_code in (404, 500) and settings.DEBUG:
            return response

        if "html" not in response["Content-Type"]:
            return response

        policy = [
            "default-src 'self'",
            f"script-src 'self' 'nonce-{request._csp_nonce}'",
            f"style-src  'self' 'nonce-{request._csp_nonce}'",
            "img-src 'self' data:",
            "frame-ancestors *",
        ]

        if settings.TIMETABLE_REPORT_URI:
            response["Reporting-Endpoints"] = (
                f'endpoint="{settings.TIMETABLE_REPORT_URI}"'
            )
            policy += [
                f"report-uri {settings.TIMETABLE_REPORT_URI}",
                "report-to endpoint",
            ]

        response["Content-Security-Policy"] = " ; ".join(policy)
        return response


class AppendSlashMiddleware(MiddlewareMixin):
    def process_request(self, request):
        # Bail if we already have trailing slash.
        if request.path.endswith("/"):
            return

        urlconf = getattr(request, "urlconf", None)
        old_is_valid = lambda: urls.is_valid_path(request.path_info, urlconf)
        new_is_valid = lambda: urls.is_valid_path("%s/" % request.path_info, urlconf)

        # Bail for valid urls or slash version not being valid.
        if old_is_valid() or not new_is_valid():
            return

        if settings.DEBUG and request.method == "POST":
            raise RuntimeError("Can't redirect POST in AppendSlashMiddleware.")

        # Redirect rest:
        url = http_utils.urlquote("%s/" % request.path_info)
        if request.META.get("QUERY_STRING", ""):
            url += "?" + request.META["QUERY_STRING"]
        return http.HttpResponsePermanentRedirect(url)


class LocaleMiddleware(MiddlewareMixin):
    def __init__(self, get_response):
        self.get_response = get_response

        self.languages = {}  # Localised semester type -> lang
        self.values = {}  # Localised semester type -> db value

        for lang, name in settings.LANGUAGES:
            with translation.override(lang):
                for value, slug in Semester.SEMESTER_SLUG:
                    self.languages[str(slug)] = lang
                    self.values[str(slug)] = value

    def process_view(self, request, view, args, kwargs):
        if "semester_type" not in kwargs:
            language = self.guess_language_from_accept_header(request)
        else:
            # Use semester type to set language, and convert localised value to
            # db value.
            try:
                semester = kwargs["semester_type"]
                language = self.languages[semester]
                kwargs["semester_type"] = self.values[semester]
            except KeyError:
                raise http.Http404

            if request.META["QUERY_STRING"] in dict(settings.LANGUAGES):
                return self.rederict_to_new_language(request, args, kwargs)

        with translation.override(language, deactivate=True):
            response = view(request, *args, **kwargs)
            response["Content-Language"] = language

        if "semester_type" not in kwargs:
            # Only set vary header when we had to guess.
            cache.patch_vary_headers(response, ("Accept-Language",))

        return response

    def guess_language_from_accept_header(self, request):
        supported = dict(settings.LANGUAGES)
        accept = request.headers.get("Accept-Language", "")

        for lang, unused in trans_internals.parse_accept_lang_header(accept):
            if lang == "*":
                break
            lang = lang.split("-")[0].lower()
            if settings.LANGUAGE_FALLBACK.get(lang, lang) in supported:
                return lang
        return settings.LANGUAGE_CODE

    def rederict_to_new_language(self, request, args, kwargs):
        # Support ?lang etc, if this is present we activate the lang and
        # resolve the current url to get its name and reverse it with a
        # localised semester type.
        with translation.override(request.META["QUERY_STRING"], deactivate=True):
            match = urls.resolve(request.path_info)
            kwargs["semester_type"] = dict(Semester.SEMESTER_SLUG)[
                kwargs["semester_type"]
            ]
            return shortcuts.redirect(match.url_name, *args, **kwargs)
