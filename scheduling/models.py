from __future__ import annotations

from datetime import timedelta

from django.db import models
from django.utils import timezone

from .constants import DAYS


def _now():
    return timezone.now()


def _title_case(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return ""
    return " ".join([w[:1].upper() + w[1:].lower() for w in s.split()])


class Staff(models.Model):
    name = models.CharField(max_length=80, unique=True)

    created_at = models.DateTimeField(default=_now)
    updated_at = models.DateTimeField(default=_now)

    def save(self, *args, **kwargs):
        self.name = _title_case(self.name)
        self.updated_at = _now()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Slot(models.Model):
    BG_SOLID = "solid"
    BG_GRADIENT = "gradient"

    key = models.SlugField(max_length=40, unique=True)
    label = models.CharField(max_length=40)
    sort_order = models.IntegerField(default=0)

    allow_block = models.BooleanField(default=False)  # only PT uses this

    bg_type = models.CharField(
        max_length=10,
        choices=[(BG_SOLID, "Solid"), (BG_GRADIENT, "Gradient")],
        default=BG_SOLID,
    )
    bg_color1 = models.CharField(max_length=20, default="#ffffff")
    bg_color2 = models.CharField(max_length=20, default="#ffffff")
    text_color = models.CharField(max_length=20, default="#111827")

    pt_default_time = models.CharField(max_length=20, blank=True, default="7-11")

    def __str__(self):
        return f"{self.sort_order} - {self.label}"


class ScheduleTheme(models.Model):
    BG_SOLID = "solid"
    BG_GRADIENT = "gradient"

    header_bg_type = models.CharField(
        max_length=10,
        choices=[(BG_SOLID, "Solid"), (BG_GRADIENT, "Gradient")],
        default=BG_GRADIENT,
    )
    header_bg_color1 = models.CharField(max_length=20, default="#0f172a")
    header_bg_color2 = models.CharField(max_length=20, default="#2563eb")
    header_text_color = models.CharField(max_length=20, default="#ffffff")

    table_header_bg = models.CharField(max_length=20, default="#f3f4f6")
    table_header_text = models.CharField(max_length=20, default="#111827")

    weekend_bg = models.CharField(max_length=20, default="#fafafa")
    blocked_bg = models.CharField(max_length=20, default="#fda4af")  # reddish

    created_at = models.DateTimeField(default=_now)
    updated_at = models.DateTimeField(default=_now)

    def save(self, *args, **kwargs):
        self.updated_at = _now()
        return super().save(*args, **kwargs)


class ScheduleWeek(models.Model):
    week_start = models.DateField(unique=True, db_index=True)  # Monday
    cells = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(default=_now)
    updated_at = models.DateTimeField(default=_now)

    def save(self, *args, **kwargs):
        if self.week_start:
            self.week_start = self.week_start - timedelta(days=self.week_start.weekday())
        self.updated_at = _now()
        return super().save(*args, **kwargs)

    def week_end(self):
        return self.week_start + timedelta(days=6)

    def date_for_day_key(self, day_key: str):
        idx = [k for k, _ in DAYS].index(day_key)
        return self.week_start + timedelta(days=idx)

    def ensure_defaults(self, *, slots: list[Slot]):
        if not isinstance(self.cells, dict):
            self.cells = {}

        for slot in slots:
            if slot.key not in self.cells or not isinstance(self.cells.get(slot.key), dict):
                self.cells[slot.key] = {}

            for day_key, _ in DAYS:
                cell = self.cells[slot.key].get(day_key)
                if not isinstance(cell, dict):
                    cell = {}

                cell.setdefault("staff", [])
                cell.setdefault("blocked", False)
                if slot.key == "pt":
                    cell.setdefault("pt_time", slot.pt_default_time or "7-11")

                self.cells[slot.key][day_key] = cell

        return self.cells
