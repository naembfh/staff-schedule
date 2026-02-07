from django.contrib import admin
from django.shortcuts import redirect
from django.urls import include, path


def root_redirect(_request):
    return redirect("/schedule/")


urlpatterns = [
    path("admin/", admin.site.urls),
    path("schedule/", include("scheduling.urls")),
    path("", root_redirect),
]
