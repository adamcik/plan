# This file is part of the plan timetable generator, see LICENSE for details.

import datetime
import gzip
import operator
import random
import re
import time
import typing
from django.utils.html import escape
import typing_extensions

from django import http, template
from django.conf import settings, urls
from django.core.cache import cache
from django.db import models
from django.utils import http as http_utils
from django.utils import text as text_utils
from django.utils import translation

_ = translation.gettext

# Collection of capture groups used in urls.
URL_ALIASES = {
    "year": r"(?P<year>\d{4})",
    "semester": r"(?P<semester_type>\w+)",
    "slug": r"(?P<slug>[a-z0-9-_]{1,50})",
    "week": r"(?P<week>\d{1,2})",
    "size": r"(?P<size>A\d)",
    "ical": r"(?P<ical_type>\w+)",
    "id": r"(?P<id>\d+)",
    "redirect_type": r"(?P<type>course|syllabus|room)",
}

RE_ACCEPTS_GZIP = re.compile(r"\bgzip\b")


def url_helper(regexp, *args, **kwargs):
    """Helper that inserts our url aliases using string formating."""
    return urls.url(regexp.format(**URL_ALIASES), *args, **kwargs)


def bypass_cache(request):
    if "no-cache" in request.GET:
        return True
    elif "no-cache" in request.headers.get("Cache-Control", ""):
        return True
    elif "no-cache" in request.headers.get("Pragma", ""):
        return True
    else:
        return False


def debug_response(response):
    content = []
    for key, value in response.headers.items():
        content.append(f"{key}: {escape(value)}")
    content.append("")

    if response.get("Content-Type", "").startswith("text/"):
        escaped = escape(response.content.decode())
        content.append(re.sub(r"\r?\n", "&#10;", escaped))
    else:
        content.append(f"Response contains {len(response.content)} encoded bytes.")

    return http.HttpResponse(
        f"<html><head></head><body><pre>{'<br/>'.join(content)}</pre></body></html>"
    )


def accepts_gzip(request):
    return RE_ACCEPTS_GZIP.search(request.META.get("HTTP_ACCEPT_ENCODING", ""))


def compress_response(response, min_size=200):
    if "Content-Encoding" in response or len(response.content) < min_size:
        return response

    content = gzip.compress(
        response.content,
        compresslevel=6,
        mtime=0,
    )

    if len(content) > len(response.content):
        return response

    result = http.HttpResponse(
        content, status=response.status_code, headers=response.headers
    )
    result.headers["Content-Length"] = str(len(content))
    result.headers["Content-Encoding"] = "gzip"

    cache_utils.patch_vary_headers(result, ("Accept-Encoding",))
    return result


def decompress_response(response):
    if response.get("Content-Encoding") != "gzip":
        return response

    result = http.HttpResponse(
        gzip.decompress(response.content),
        status=response.status_code,
        headers=response.headers,
    )
    cache_utils.patch_vary_headers(result, ("Accept-Encoding",))
    response.headers["Content-Length"] = str(len(response.content))
    del response.headers["Content-Encoding"]
    return result


def check_modified_since(request, last_modified):
    if_modified_since = http_utils.parse_http_date_safe(
        request.META.get("HTTP_IF_MODIFIED_SINCE"),
    )

    if (
        "no-modified-since" in request.GET
        or if_modified_since is None
        or last_modified > if_modified_since
    ):
        return None
    return http.HttpResponseNotModified(
        headers={"Last-Modified": http_utils.http_date(last_modified)}
    )


def cache_headers(timeout: datetime.timedelta, jitter: float = 0.0) -> dict[str, str]:
    seconds = timeout.total_seconds()
    if jitter > 0:
        seconds += random.uniform(0, seconds * jitter)

    return {
        "Expires": http_utils.http_date(time.time() + seconds),
        "Cache-Control": "max-age=%d" % seconds,
    }


def ical_filename(year, semester_type, slug, resources):
    return "%s.ics" % "-".join([year, semester_type, slug] + resources)


def clear_cache(year, semester_type, slug):
    cache.delete_many(
        [
            ical_filename(year, semester_type, slug, [_("lectures"), _("exams")]),
            ical_filename(year, semester_type, slug, [_("lectures")]),
            ical_filename(year, semester_type, slug, [_("exams")]),
        ]
    )


Params = typing_extensions.ParamSpec("Params")
ViewDecorator = typing.Callable[Params, http.HttpResponse]


def expires_in(timeout: datetime.timedelta):
    def decorator(func: ViewDecorator[Params]) -> ViewDecorator[Params]:
        def wrapper(*args: Params.args, **kwargs: Params.kwargs) -> http.HttpResponse:
            response = func(*args, **kwargs)
            for name, value in cache_headers(timeout).items():
                response.headers[name] = value
            return response

        return wrapper

    return decorator


def parse_query(querystring):
    terms = []
    for word in text_utils.smart_split(querystring):
        if word[0] in ['"', "'"]:
            if word[0] == word[-1]:
                word = word[1:-1]
            else:
                word = word[1:]

        terms.append(word)
    return terms


def build_search(terms, filters, max_query_length=4, combine=operator.and_):
    search_filter = models.Q()

    for term in terms[:max_query_length]:
        local_filter = models.Q()
        for f in filters:
            local_filter |= models.Q(**{f: term})
        search_filter = combine(search_filter, local_filter)

    return search_filter


def server_error(request, template_name="500.html"):
    """
    500 error handler.

    Templates: `500.html`
    Context: None
    """
    # You need to create a 500.html template.
    t = template.loader.get_template(template_name)

    return http.HttpResponseServerError(
        t.render(
            {
                "MEDIA_URL": settings.MEDIA_URL,
                "STATIC_URL": settings.STATIC_URL,
                "SOURCE_URL": settings.TIMETABLE_SOURCE_URL,
            }
        )
    )


def compact_sequence(sequence):
    """Compact sequences of numbers into array of strings [i, j, k-l, n-m]"""
    if not sequence:
        return []

    sequence.sort()

    compact = []
    first = sequence[0]
    last = sequence[0] - 1

    for item in sequence:
        if last == item - 1:
            last = item
        else:
            if first != last:
                compact.append("%d-%d" % (first, last))
            else:
                compact.append("%d" % first)

            first = item
            last = item

    if first != last:
        compact.append("%d-%d" % (first, last))
    else:
        compact.append("%d" % first)

    return compact


class ColorMap(dict):
    """Magic dict that assigns colors"""

    # Colors from www.ColorBrewer.org by Cynthia A. Brewer, Geography,
    # Pennsylvania State University.
    # http://www.personal.psu.edu/cab38/ColorBrewer/ColorBrewer_updates.html

    def __init__(self, index=0, hex=False):
        self.index = index
        self.max = len(settings.TIMETABLE_COLORS)
        self.hex = hex

    def __getitem__(self, k):
        # Remember to use super to prevent inf loop
        if k is None:
            return ""

        if k in self:
            return super().__getitem__(k)
        else:
            self.index += 1
            if self.hex:
                self[k] = settings.TIMETABLE_COLORS[self.index % self.max]
            else:
                self[k] = "color%d" % (self.index % self.max)
            return super().__getitem__(k)


def max_number_of_weeks(year):
    # dec. 28 is always on the last week if the year.
    return datetime.date(int(year), 12, 28).isocalendar()[1]


def first_date_in_week(year, week):
    if datetime.date(year, 1, 4).isoweekday() > 4:
        return datetime.datetime.strptime("%d %d 1" % (year, week - 1), "%Y %W %w")
    else:
        return datetime.datetime.strptime("%d %d 1" % (year, week), "%Y %W %w")


def natural_sort(values, key=None):
    if key is None:
        key = lambda k: k
    split = lambda v: re.split(r"(\d+)", v) if isinstance(v, str) else [v]
    convert = lambda v: int(v) if v.isdigit() else v.lower()
    return sorted(
        values,
        key=lambda v: [convert(p) if isinstance(p, str) else p for p in split(key(v))],
    )
