from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.urls import path

from plan.common.middleware import AppendSlashMiddleware


def _dummy_view(request):
    return HttpResponse("ok")


urlpatterns = [
    path("foo/", _dummy_view),
]


@override_settings(ROOT_URLCONF="plan.common.tests.test_middleware", DEBUG=False)
class AppendSlashMiddlewareTests(SimpleTestCase):
    def test_redirects_to_slash_appended_url(self):
        request = RequestFactory().get("/foo")

        response = AppendSlashMiddleware(
            lambda req: HttpResponse("ok")
        ).process_request(request)

        self.assertEqual(response.status_code, 301)
        self.assertEqual(response["Location"], "/foo/")
