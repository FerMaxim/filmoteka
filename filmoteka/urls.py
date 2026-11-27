from accounts.views import SignInView, SignOutView
from catalog import views as catalog_views

from django.db import DatabaseError, connection
from django.http import JsonResponse
from django.urls import path
from django.views.generic import TemplateView
from django.views.decorators.http import require_safe


@require_safe
def live(request):
    return JsonResponse({"status": "ok"})


@require_safe
def ready(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except DatabaseError:
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ready"})


urlpatterns = [path("health/live", live), path("health/ready", ready)]

urlpatterns += [
    path("", TemplateView.as_view(template_name="prototype.html")),
    path("prototype/", TemplateView.as_view(template_name="prototype.html")),
]


urlpatterns += [
    path("accounts/login/", SignInView.as_view()),
    path("accounts/logout/", SignOutView.as_view()),
    path("catalog/", catalog_views.catalog),
    path("works/<int:pk>/", catalog_views.detail),
    path("me/library/", catalog_views.library),
    path("me/works/<int:pk>/library/", catalog_views.add),
]
