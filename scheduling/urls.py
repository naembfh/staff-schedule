from django.urls import path

from . import views

app_name = "scheduling"

urlpatterns = [
    path("", views.home, name="home"),
    path("staff/", views.staff_page, name="staff"),
    path("staff/<int:staff_id>/delete/", views.staff_delete, name="staff_delete"),

    path("slots/", views.slots_page, name="slots"),
    path("slots/<int:slot_id>/delete/", views.slot_delete, name="slot_delete"),

    path("theme/", views.theme_page, name="theme"),

    path("week/<str:week_start>/", views.week_editor, name="week_editor"),
    path("week/<str:week_start>/pdf/", views.week_pdf, name="week_pdf"),
    path("week/<str:week_start>/png/", views.week_png, name="week_png"),

    path("api/week/<str:week_start>/cell/update/", views.api_cell_update, name="api_cell_update"),
    path("api/week/<str:week_start>/cell/block/", views.api_cell_block, name="api_cell_block"),
]
