from django.http import HttpResponse
from django.urls import path

from plan.common.middleware import AppendSlashMiddleware


def _dummy_view(request):
    return HttpResponse("ok")


urlpatterns = [
    path("foo/", _dummy_view),
]


def test_redirects_to_slash_appended_url(settings, rf):
    settings.ROOT_URLCONF = "plan.common.tests.test_middleware"
    settings.DEBUG = False
    request = rf.get("/foo")

    response = AppendSlashMiddleware(lambda req: HttpResponse("ok")).process_request(
        request
    )

    assert response.status_code == 301
    assert response["Location"] == "/foo/"
