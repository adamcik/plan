# This file is part of the plan timetable generator, see LICENSE for details.

import datetime
import operator
import random
import re
import time
import typing
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
}


def url_helper(regexp, *args, **kwargs):
    """Helper that inserts our url aliases using string formating."""
    return urls.url(regexp.format(**URL_ALIASES), *args, **kwargs)


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


def build_search(searchstring, filters, max_query_length=4, combine=operator.and_):
    count = 0
    search_filter = models.Q()

    for word in text_utils.smart_split(searchstring):
        if word[0] in ['"', "'"]:
            if word[0] == word[-1]:
                word = word[1:-1]
            else:
                word = word[1:]

        if count > max_query_length:
            break

        local_filter = models.Q()
        for f in filters:
            local_filter |= models.Q(**{f: word})

        search_filter = combine(search_filter, local_filter)
        count += 1

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
