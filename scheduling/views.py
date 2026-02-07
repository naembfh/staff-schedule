from __future__ import annotations

import json
from datetime import datetime, timedelta

from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .constants import DAYS, EXCLUSIVE_SLOT_KEYS, PT_SLOT_KEY
from .exports import build_pdf, build_png
from .models import ScheduleTheme, ScheduleWeek, Slot, Staff


def _monday(d):
    return d - timedelta(days=d.weekday())


def _json_body(request):
    try:
        return json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        return {}


def _unique_keep_order(items):
    seen = set()
    out = []
    for x in items:
        if x in seen:
            continue
        seen.add(x)
        out.append(x)
    return out


def _get_theme():
    theme = ScheduleTheme.objects.order_by("id").first()
    if not theme:
        theme = ScheduleTheme.objects.create()
    return theme


def home(request):
    if request.method == "POST" and request.POST.get("open_week"):
        date_str = (request.POST.get("date") or "").strip()
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
        monday = _monday(d)
        ScheduleWeek.objects.get_or_create(week_start=monday)
        return redirect("scheduling:week_editor", week_start=monday.isoformat())

    weeks = ScheduleWeek.objects.order_by("-week_start")[:40]
    today = datetime.now().date().isoformat()
    return render(request, "scheduling/home.html", {
        "weeks": weeks,
        "today": today,
        "theme": _get_theme(),
    })


def staff_page(request):
    error = ""

    if request.method == "POST" and request.POST.get("add_staff"):
        name = (request.POST.get("name") or "").strip()
        if not name:
            error = "Name is required."
        else:
            try:
                Staff.objects.create(name=name)
                return redirect("scheduling:staff")
            except Exception:
                error = "This name already exists."

    staff = Staff.objects.order_by("name")
    return render(request, "scheduling/staff.html", {
        "staff": staff,
        "error": error,
        "theme": _get_theme(),
    })


@require_POST
def staff_delete(request, staff_id: int):
    staff = get_object_or_404(Staff, id=staff_id)

    # Remove from all weeks
    for sched in ScheduleWeek.objects.all():
        if not isinstance(sched.cells, dict):
            continue
        changed = False
        for slot_key, day_map in (sched.cells or {}).items():
            if not isinstance(day_map, dict):
                continue
            for day_key in list(day_map.keys()):
                cell = day_map.get(day_key) or {}
                if not isinstance(cell, dict):
                    continue
                ids = [int(x) for x in (cell.get("staff") or []) if str(x).isdigit()]
                new_ids = [x for x in ids if x != staff.id]
                if new_ids != ids:
                    cell["staff"] = new_ids
                    sched.cells[slot_key][day_key] = cell
                    changed = True
        if changed:
            sched.save()

    staff.delete()
    return redirect("scheduling:staff")


def slots_page(request):
    theme = _get_theme()
    slots = Slot.objects.order_by("sort_order", "label")
    error = ""

    if request.method == "POST" and request.POST.get("add_slot"):
        label = (request.POST.get("label") or "").strip()
        key = (request.POST.get("key") or "").strip()
        sort_order = (request.POST.get("sort_order") or "0").strip()
        allow_block = bool(request.POST.get("allow_block"))

        bg_type = (request.POST.get("bg_type") or Slot.BG_SOLID).strip()
        bg_color1 = (request.POST.get("bg_color1") or "#ffffff").strip()
        bg_color2 = (request.POST.get("bg_color2") or bg_color1).strip()
        text_color = (request.POST.get("text_color") or "#111827").strip()
        pt_default_time = (request.POST.get("pt_default_time") or "7-11").strip()

        if not label or not key:
            error = "Label and key are required."
        else:
            try:
                Slot.objects.create(
                    label=label,
                    key=key,
                    sort_order=int(sort_order or 0),
                    allow_block=allow_block,
                    bg_type=bg_type,
                    bg_color1=bg_color1,
                    bg_color2=bg_color2,
                    text_color=text_color,
                    pt_default_time=pt_default_time,
                )
                return redirect("scheduling:slots")
            except Exception:
                error = "Slot key must be unique."

    if request.method == "POST" and request.POST.get("update_slot"):
        slot_id = int(request.POST.get("slot_id") or 0)
        slot = get_object_or_404(Slot, id=slot_id)

        slot.label = (request.POST.get("label") or slot.label).strip()
        slot.sort_order = int((request.POST.get("sort_order") or slot.sort_order) or 0)
        slot.allow_block = bool(request.POST.get("allow_block"))

        slot.bg_type = (request.POST.get("bg_type") or slot.bg_type).strip()
        slot.bg_color1 = (request.POST.get("bg_color1") or slot.bg_color1).strip()
        slot.bg_color2 = (request.POST.get("bg_color2") or slot.bg_color2).strip()
        slot.text_color = (request.POST.get("text_color") or slot.text_color).strip()

        if slot.key == PT_SLOT_KEY:
            slot.pt_default_time = (request.POST.get("pt_default_time") or slot.pt_default_time).strip()

        slot.save()
        return redirect("scheduling:slots")

    return render(request, "scheduling/slots.html", {
        "slots": slots,
        "error": error,
        "theme": theme,
        "pt_key": PT_SLOT_KEY,
    })


@require_POST
def slot_delete(request, slot_id: int):
    slot = get_object_or_404(Slot, id=slot_id)
    slot.delete()
    return redirect("scheduling:slots")


def theme_page(request):
    theme = _get_theme()
    if request.method == "POST" and request.POST.get("save_theme"):
        theme.header_bg_type = (request.POST.get("header_bg_type") or theme.header_bg_type).strip()
        theme.header_bg_color1 = (request.POST.get("header_bg_color1") or theme.header_bg_color1).strip()
        theme.header_bg_color2 = (request.POST.get("header_bg_color2") or theme.header_bg_color2).strip()
        theme.header_text_color = (request.POST.get("header_text_color") or theme.header_text_color).strip()

        theme.table_header_bg = (request.POST.get("table_header_bg") or theme.table_header_bg).strip()
        theme.table_header_text = (request.POST.get("table_header_text") or theme.table_header_text).strip()

        theme.weekend_bg = (request.POST.get("weekend_bg") or theme.weekend_bg).strip()
        theme.blocked_bg = (request.POST.get("blocked_bg") or theme.blocked_bg).strip()

        theme.save()
        return redirect("scheduling:theme")

    return render(request, "scheduling/theme.html", {"theme": theme})


def week_editor(request, week_start: str):
    theme = _get_theme()
    week_start_date = _monday(datetime.strptime(week_start, "%Y-%m-%d").date())
    schedule, _ = ScheduleWeek.objects.get_or_create(week_start=week_start_date)

    slots = list(Slot.objects.order_by("sort_order", "label"))
    schedule.ensure_defaults(slots=slots)
    schedule.save()

    if request.method == "POST" and request.POST.get("save_notes"):
        schedule.notes = (request.POST.get("notes") or "").strip()
        schedule.save()
        return redirect("scheduling:week_editor", week_start=schedule.week_start.isoformat())

    staff = list(Staff.objects.order_by("name"))
    staff_map = {s.id: s.name for s in staff}

    day_headers = []
    for day_key, day_label in DAYS:
        d = schedule.date_for_day_key(day_key)
        day_headers.append({
            "key": day_key,
            "label": day_label,
            "date_str": d.strftime("%d %b"),
        })

    prev_week = (schedule.week_start - timedelta(days=7)).isoformat()
    next_week = (schedule.week_start + timedelta(days=7)).isoformat()

    return render(request, "scheduling/week_editor.html", {
        "theme": theme,
        "schedule": schedule,
        "slots": slots,
        "staff": staff,
        "staff_map": staff_map,
        "day_headers": day_headers,
        "prev_week": prev_week,
        "next_week": next_week,
        "week_start": schedule.week_start.isoformat(),
    })


def _is_staff_assigned_anywhere(schedule: ScheduleWeek, *, day_key: str, staff_id: int) -> bool:
    for slot_key, day_map in (schedule.cells or {}).items():
        if slot_key in EXCLUSIVE_SLOT_KEYS:
            continue
        cell = (day_map or {}).get(day_key, {}) or {}
        ids = [int(x) for x in (cell.get("staff") or []) if str(x).isdigit()]
        if staff_id in ids:
            return True
    return False


def _is_staff_in_exclusive(schedule: ScheduleWeek, *, day_key: str, staff_id: int) -> bool:
    for ex_key in EXCLUSIVE_SLOT_KEYS:
        cell = (schedule.cells.get(ex_key, {}) or {}).get(day_key, {}) or {}
        ids = [int(x) for x in (cell.get("staff") or []) if str(x).isdigit()]
        if staff_id in ids:
            return True
    return False


@require_POST
def api_cell_update(request, week_start: str):
    week_start_date = _monday(datetime.strptime(week_start, "%Y-%m-%d").date())
    schedule = get_object_or_404(ScheduleWeek, week_start=week_start_date)

    payload = _json_body(request)
    slot_key = (payload.get("slot_key") or "").strip()
    day_key = (payload.get("day_key") or "").strip()
    action = (payload.get("action") or "").strip()

    staff_id = payload.get("staff_id")
    pt_time = payload.get("pt_time")

    slot = get_object_or_404(Slot, key=slot_key)

    valid_day_keys = {k for k, _ in DAYS}
    if day_key not in valid_day_keys:
        return JsonResponse({"ok": False, "error": "Invalid day."}, status=400)

    schedule.ensure_defaults(slots=list(Slot.objects.order_by("sort_order", "label")))

    cell = schedule.cells[slot_key][day_key]

    if slot.allow_block and bool(cell.get("blocked")) and action in ("add", "remove"):
        return JsonResponse({"ok": False, "error": "This cell is blocked."}, status=409)

    if action == "set_pt_time":
        if slot_key != PT_SLOT_KEY:
            return JsonResponse({"ok": False, "error": "PT time only applies to PT row."}, status=400)
        cell["pt_time"] = (pt_time or "").strip()
        schedule.cells[slot_key][day_key] = cell
        schedule.save()
        return JsonResponse({"ok": True, "staff_ids": cell.get("staff") or [], "pt_time": cell.get("pt_time") or "", "blocked": bool(cell.get("blocked"))})

    if staff_id is None:
        return JsonResponse({"ok": False, "error": "Missing staff_id."}, status=400)

    try:
        staff_id = int(staff_id)
    except Exception:
        return JsonResponse({"ok": False, "error": "Invalid staff_id."}, status=400)

    if not Staff.objects.filter(id=staff_id).exists():
        return JsonResponse({"ok": False, "error": "Staff not found."}, status=404)

    ids = [int(x) for x in (cell.get("staff") or []) if str(x).isdigit()]
    ids = _unique_keep_order(ids)

    if action == "add":
        # Off/Leave rules
        if slot_key not in EXCLUSIVE_SLOT_KEYS:
            if _is_staff_in_exclusive(schedule, day_key=day_key, staff_id=staff_id):
                return JsonResponse({"ok": False, "error": "Not allowed: staff is Off Day / PH-AL on this day."}, status=409)

            # No multiple-time assignment on same day
            if _is_staff_assigned_anywhere(schedule, day_key=day_key, staff_id=staff_id):
                return JsonResponse({"ok": False, "error": "Not allowed: staff already assigned on this day."}, status=409)

        if staff_id not in ids:
            ids.append(staff_id)
        cell["staff"] = ids
        schedule.cells[slot_key][day_key] = cell

        # If adding to exclusive row, remove from all other rows that day
        if slot_key in EXCLUSIVE_SLOT_KEYS:
            for other_slot_key, day_map in (schedule.cells or {}).items():
                if other_slot_key == slot_key:
                    continue
                other_cell = (day_map or {}).get(day_key, {}) or {}
                other_ids = [int(x) for x in (other_cell.get("staff") or []) if str(x).isdigit()]
                new_other = [x for x in other_ids if x != staff_id]
                if new_other != other_ids:
                    other_cell["staff"] = new_other
                    schedule.cells[other_slot_key][day_key] = other_cell

        schedule.save()
        return JsonResponse({"ok": True, "staff_ids": cell.get("staff") or [], "pt_time": cell.get("pt_time") or "", "blocked": bool(cell.get("blocked"))})

    if action == "remove":
        new_ids = [x for x in ids if x != staff_id]
        cell["staff"] = new_ids
        schedule.cells[slot_key][day_key] = cell
        schedule.save()
        return JsonResponse({"ok": True, "staff_ids": cell.get("staff") or [], "pt_time": cell.get("pt_time") or "", "blocked": bool(cell.get("blocked"))})

    return JsonResponse({"ok": False, "error": "Invalid action."}, status=400)


@require_POST
def api_cell_block(request, week_start: str):
    week_start_date = _monday(datetime.strptime(week_start, "%Y-%m-%d").date())
    schedule = get_object_or_404(ScheduleWeek, week_start=week_start_date)

    payload = _json_body(request)
    slot_key = (payload.get("slot_key") or "").strip()
    day_key = (payload.get("day_key") or "").strip()

    slot = get_object_or_404(Slot, key=slot_key)
    if not slot.allow_block:
        return JsonResponse({"ok": False, "error": "This slot cannot be blocked."}, status=400)

    schedule.ensure_defaults(slots=list(Slot.objects.order_by("sort_order", "label")))

    cell = schedule.cells[slot_key][day_key]
    blocked = not bool(cell.get("blocked"))
    cell["blocked"] = blocked
    if blocked:
        cell["staff"] = []
    schedule.cells[slot_key][day_key] = cell
    schedule.save()

    return JsonResponse({"ok": True, "staff_ids": cell.get("staff") or [], "pt_time": cell.get("pt_time") or "", "blocked": bool(cell.get("blocked"))})


def week_pdf(request, week_start: str):
    theme = _get_theme()
    week_start_date = _monday(datetime.strptime(week_start, "%Y-%m-%d").date())
    schedule = get_object_or_404(ScheduleWeek, week_start=week_start_date)

    slots = list(Slot.objects.order_by("sort_order", "label"))
    schedule.ensure_defaults(slots=slots)

    staff_map = {s.id: s.name for s in Staff.objects.all()}
    style = int(request.GET.get("style") or 1)
    pdf_bytes = build_pdf(schedule=schedule, slots=slots, staff_map=staff_map, theme=theme, style=style)

    resp = HttpResponse(pdf_bytes, content_type="application/pdf")
    resp["Content-Disposition"] = f'attachment; filename="schedule_{schedule.week_start}.pdf"'
    return resp


def week_png(request, week_start: str):
    theme = _get_theme()
    week_start_date = _monday(datetime.strptime(week_start, "%Y-%m-%d").date())
    schedule = get_object_or_404(ScheduleWeek, week_start=week_start_date)

    slots = list(Slot.objects.order_by("sort_order", "label"))
    schedule.ensure_defaults(slots=slots)

    staff_map = {s.id: s.name for s in Staff.objects.all()}
    dpi = int(request.GET.get("dpi") or 450)
    style = int(request.GET.get("style") or 1)

    png_bytes = build_png(schedule=schedule, slots=slots, staff_map=staff_map, theme=theme, dpi=dpi, style=style)

    resp = HttpResponse(png_bytes, content_type="image/png")
    resp["Content-Disposition"] = f'attachment; filename="schedule_{schedule.week_start}_{dpi}dpi.png"'
    return resp
