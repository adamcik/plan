# This file is part of the plan timetable generator, see LICENSE for details.

import gzip
import re
import secrets
from urllib.parse import quote

import brotli

from django import http, shortcuts, urls
from django.conf import settings
from django.http.request import HttpRequest
from django.utils import cache, translation
from django.utils.deprecation import MiddlewareMixin
from django.utils.html import escape
from django.utils.translation import trans_real as trans_internals

from plan.common.models import Semester
from plan.common.utils import parse_accepts

RE_WHITESPACE = re.compile(rb"(\s\s+|\n)")
SEMESTER_ALIASES = {
    "autum": Semester.FALL,
    "autmn": Semester.FALL,
    "autumn": Semester.FALL,
}
SEMESTER_ALIAS_PATTERN = re.compile(
    r"^/(?P<year>\d{4})/(?P<slug>[a-z]+)(?P<suffix>/.*)?$"
)


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
        response.headers["Content-Length"] = len(response.content)
        return response


class CspMiddleware(MiddlewareMixin):
    SCRIPT_NONCE_HEADER = "X-CSP-Script-Nonce"
    STYLE_NONCE_HEADER = "X-CSP-Style-Nonce"

    def process_request(self, request):
        request._csp_script_nonce = secrets.token_urlsafe(16)
        request._csp_style_nonce = secrets.token_urlsafe(16)

    @staticmethod
    def store_nonce_in_header(request, response):
        # Hack to make sure caching responses with nonce works
        response[CspMiddleware.SCRIPT_NONCE_HEADER] = request._csp_script_nonce
        response[CspMiddleware.STYLE_NONCE_HEADER] = request._csp_style_nonce

    def process_response(self, request, response):
        if response.status_code in (404, 500) and settings.DEBUG:
            return response

        if "html" not in response.get("Content-Type", ""):
            return response

        if CspMiddleware.SCRIPT_NONCE_HEADER in response:
            script_nonce = response[CspMiddleware.SCRIPT_NONCE_HEADER]
            del response[CspMiddleware.SCRIPT_NONCE_HEADER]
        else:
            script_nonce = request._csp_script_nonce

        if CspMiddleware.STYLE_NONCE_HEADER in response:
            style_nonce = response[CspMiddleware.STYLE_NONCE_HEADER]
            del response[CspMiddleware.STYLE_NONCE_HEADER]
        else:
            style_nonce = request._csp_style_nonce

        policy = [
            "default-src 'self'",
            f"script-src 'self' 'nonce-{script_nonce}'",
            f"style-src  'self' 'nonce-{style_nonce}'",
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

        def old_is_valid():
            return urls.is_valid_path(request.path_info, urlconf)

        def new_is_valid():
            return urls.is_valid_path("%s/" % request.path_info, urlconf)

        # Bail for valid urls or slash version not being valid.
        if old_is_valid() or not new_is_valid():
            return

        if settings.DEBUG and request.method == "POST":
            raise RuntimeError("Can't redirect POST in AppendSlashMiddleware.")

        # Redirect rest:
        url = quote("%s/" % request.path_info, safe="/")
        if request.META.get("QUERY_STRING", ""):
            url += "?" + request.META["QUERY_STRING"]
        return http.HttpResponsePermanentRedirect(url)


def _guess_language_from_accept_header(request):
    supported = dict(settings.LANGUAGES)
    accept = request.headers.get("Accept-Language", "")

    for lang, unused in trans_internals.parse_accept_lang_header(accept):
        if lang == "*":
            break
        lang = lang.split("-")[0].lower()
        if settings.LANGUAGE_FALLBACK.get(lang, lang) in supported:
            return lang
    return settings.LANGUAGE_CODE


def _redirect_to_new_language(request, language):
    # Support ?lang etc, if this is present we activate the lang and
    # resolve the current url to get its name and reverse it with a
    # localised semester type.
    with translation.override(language, deactivate=True):
        match = urls.resolve(request.path_info)
        return shortcuts.redirect(match.url_name, *match.args, **match.kwargs)


def _redirect_semester_alias(request):
    match = SEMESTER_ALIAS_PATTERN.match(request.path_info)
    if not match or match.group("slug") not in SEMESTER_ALIASES:
        return None

    semester_type = SEMESTER_ALIASES[match.group("slug")]
    suffix = match.group("suffix") or ""
    url = f"/{match.group('year')}/{Semester.localize(semester_type)}{suffix}"
    if request.META.get("QUERY_STRING", ""):
        url += "?" + request.META["QUERY_STRING"]
    return http.HttpResponsePermanentRedirect(url)


def locale_middleware(get_response):
    LANGUAGES = {l for l, _ in settings.LANGUAGES}

    SLUGS = {}  # Map localized slug to language
    for lang, _ in settings.LANGUAGES:
        with translation.override(lang):
            for slug in Semester.SEMESTER_SLUG.values():
                SLUGS[str(slug)] = lang

    PATTERN = re.compile(rf"^/\d+/({'|'.join(re.escape(s) for s in SLUGS)})/")

    def middleware(request: HttpRequest):
        lang = request.META["QUERY_STRING"]
        if lang in LANGUAGES:
            return _redirect_to_new_language(request, lang)

        match = PATTERN.match(request.path_info)
        if not match:
            lang = _guess_language_from_accept_header(request)
        else:
            lang = SLUGS[match.group(1)]

        with translation.override(lang, deactivate=True):
            redirect = _redirect_semester_alias(request)
            if redirect:
                return redirect
            response = get_response(request)
            response["Content-Language"] = lang

        if not match:  # Only set vary header when we had to guess.
            cache.patch_vary_headers(response, ("Accept-Language",))

        return response

    return middleware


def text_debug_middleware(get_response):
    """Debug middleware that turns non-html and/or downloads into "HTML"

    This is meant for development and in combination with django debug toolbar.
    Allowing us to see all the info for e.g. PDF and ICAL views.
    """

    def middleware(request):
        response = get_response(request)

        if not settings.DEBUG or "debug" not in request.GET:
            return response

        content_type = response.get("Content-Type", "")
        content_encoding = response.get("Content-Encoding", "")

        if content_type.startswith("text/html"):
            return response

        content = []
        for key, value in response.headers.items():
            content.append(f"{key}: {escape(value)}")
        content.append("")

        if content_type.startswith("text/"):
            if content_encoding == "gzip":
                response.content = gzip.decompress(response.content)
            elif content_encoding == "br":
                response.content = brotli.decompress(response.content)

            escaped = escape(response.content.decode())
            content.append(re.sub(r"\r?\n", "&#10;", escaped))
        else:
            content.append(f"Non text response contains {len(response.content)} bytes.")

        return http.HttpResponse(
            f"<html><head></head><body><pre>{'<br/>'.join(content)}</pre></body></html>"
        )

    return middleware


def encoding_compatibility_middleware(get_response):
    """Automatically decode content if not supported by client.

    This allows us to store compressed content in caches which saves space and
    given how widely supported br/gzip is, we hardly ever hit this code path.
    """

    def middleware(request):
        response = get_response(request)
        cache.patch_vary_headers(response, ("Accept-Encoding",))

        encoding = response.headers.get("Content-Encoding")
        accepts = parse_accepts(request)

        if encoding == "br" and "br" not in accepts:
            content = brotli.decompress(response.content)
        elif encoding == "gzip" and "gzip" not in accepts:
            content = gzip.decompress(response.content)
        else:
            return response

        response = http.HttpResponse(
            content, status=response.status_code, headers=response.headers
        )
        response.headers["Content-Length"] = str(len(response.content))
        del response.headers["Content-Encoding"]

        return response

    return middleware
