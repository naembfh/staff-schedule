from django.contrib import admin

from .models import ScheduleTheme, ScheduleWeek, Slot, Staff


@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = ("name", "created_at")
    search_fields = ("name",)


@admin.register(Slot)
class SlotAdmin(admin.ModelAdmin):
    # In Django admin, the first field in list_display cannot be list_editable
    # unless list_display_links is explicitly set. We keep inline ordering edits
    # by making "label" the clickable link and keeping "sort_order" editable.
    list_display = ("label", "sort_order", "key", "allow_block", "bg_type")
    list_display_links = ("label",)
    list_editable = ("sort_order",)
    search_fields = ("label", "key")


@admin.register(ScheduleWeek)
class ScheduleWeekAdmin(admin.ModelAdmin):
    list_display = ("week_start", "created_at", "updated_at")
    search_fields = ("week_start",)


@admin.register(ScheduleTheme)
class ScheduleThemeAdmin(admin.ModelAdmin):
    list_display = ("id", "header_bg_type", "updated_at")
