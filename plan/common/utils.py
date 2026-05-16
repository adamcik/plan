# This file is part of the plan timetable generator, see LICENSE for details.

import datetime
import gzip
import hashlib
import operator
import random
import re
import time
import typing
import urllib.parse

import brotli
import typing_extensions

from django import http, template
from django.conf import settings
from django.core.cache import cache
from django.db import models
from django.utils import cache as cache_utils
from django.utils import http as http_utils
from django.utils import text as text_utils
from django.utils import translation

from plan.common.schedule import Schedule
from plan.common.snapshot import ScheduleSnapshot

_ = translation.gettext


# FIXME: This needs to match the converter, or be property of the schedule?
def clear_cache(
    schedule: Schedule,
):
    year = schedule.semester.year
    semester_type = schedule.semester.type
    slug = schedule.student.slug

    cache.delete(f"schedule:{year}-{semester_type}-{slug}")


# TODO: Only allow bypass in DEBUG?
def should_bypass_cache(request):
    if "no-cache" in request.GET:
        return True
    elif "no-cache" in request.headers.get("Cache-Control", ""):
        return True
    elif "no-cache" in request.headers.get("Pragma", ""):
        return True
    else:
        return False


def parse_accepts(request):
    accepts = request.META.get("HTTP_ACCEPT_ENCODING", "")
    return {p.split(";")[0].strip().lower() for p in accepts.split(",")}


def compress_response(request, response, min_size=200):
    if "Content-Encoding" in response or len(response.content) < min_size:
        return response

    accepts = parse_accepts(request)
    if "br" in accepts:
        content = brotli.compress(response.content, brotli.MODE_TEXT)
        encoding = "br"
    elif "gzip" in accepts:
        content = gzip.compress(
            response.content,
            compresslevel=6,
            mtime=0,
        )
        encoding = "gzip"
    else:
        return response

    if len(content) > len(response.content):
        return response

    response = http.HttpResponse(
        content, status=response.status_code, headers=response.headers
    )
    response.headers["Content-Length"] = str(len(content))
    response.headers["Content-Encoding"] = encoding

    cache_utils.patch_vary_headers(response, ("Accept-Encoding",))
    return response


def check_modified_since(request, last_modified, headers=None):
    if not settings.TIMETABLE_ENABLE_IF_MODIFIED_SINCE:
        return None

    if "no-modified-since" in request.GET:
        return None

    if last_modified is None or last_modified <= 0:
        return None

    if_modified_since = http_utils.parse_http_date_safe(
        request.META.get("HTTP_IF_MODIFIED_SINCE")
    )
    if if_modified_since is None:
        return None

    if last_modified > if_modified_since:
        return None
    return http.HttpResponseNotModified(headers=headers or {})


def etag_for_key(key: str) -> str:
    return f'"{hashlib.sha256(key.encode()).hexdigest()}"'


def response_cache_key(route: str, freshness: str, *parts: str) -> str:
    return ":".join(("resp", route, freshness, *parts))


def if_none_match_matches(request, etag: str) -> bool:
    if_none_match = request.META.get("HTTP_IF_NONE_MATCH")
    if if_none_match is None:
        return False

    etags = http_utils.parse_etags(if_none_match)
    return "*" in etags or etag in etags


def check_not_modified(request, last_modified, response_headers=None):
    if response_headers is None:
        response_headers = {}
    etag = response_headers.get("ETag")

    if "HTTP_IF_NONE_MATCH" in request.META:
        if etag and if_none_match_matches(request, etag):
            return http.HttpResponseNotModified(headers=response_headers)
        return None

    return check_modified_since(request, last_modified, response_headers)


def cache_headers(timeout: datetime.timedelta, jitter: float = 0.0) -> dict[str, str]:
    seconds = timeout.total_seconds()
    if jitter > 0:
        seconds += random.uniform(0, seconds * jitter)

    return {
        "Expires": http_utils.http_date(time.time() + seconds),
        "Cache-Control": "max-age=%d" % seconds,
    }


def ical_filename(snapshot: ScheduleSnapshot, resources):
    parts = [
        snapshot.semester.year,
        snapshot.semester.type,
        snapshot.student.slug,
        *resources,
    ]
    return "%s.ics" % "-".join(str(v) for v in parts)


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

        def key(k):
            return k

    def split(v):
        return re.split(r"(\d+)", v) if isinstance(v, str) else [v]

    def convert(v):
        return int(v) if v.isdigit() else v.lower()

    return sorted(
        values,
        key=lambda v: [convert(p) if isinstance(p, str) else p for p in split(key(v))],
    )


def update_url_params(url, params):
    parts = list(urllib.parse.urlparse(url))
    query = dict(urllib.parse.parse_qsl(parts[4]))
    query.update(params)
    parts[4] = urllib.parse.urlencode(query)
    return urllib.parse.urlunparse(parts)
