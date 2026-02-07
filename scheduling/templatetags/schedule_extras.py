from __future__ import annotations

from django import template

register = template.Library()


@register.filter
def get_item(d, key):
    if isinstance(d, dict):
        return d.get(key)
    return None


@register.filter
def get_dict(d, key):
    if isinstance(d, dict):
        v = d.get(key)
        if isinstance(v, dict):
            return v
    return {}


@register.filter
def get_list(d, key):
    if isinstance(d, dict):
        v = d.get(key)
        if isinstance(v, list):
            return v
    return []


@register.filter
def get_bool(d, key):
    if isinstance(d, dict):
        return bool(d.get(key))
    return False


@register.filter
def get_str(d, key):
    if isinstance(d, dict):
        v = d.get(key)
        if v is None:
            return ""
        return str(v)
    return ""


@register.filter
def style_bg(slot):
    try:
        if getattr(slot, "bg_type", "") == "gradient":
            return f"background-image: linear-gradient(90deg, {slot.bg_color1}, {slot.bg_color2}); color: {slot.text_color};"
        return f"background-color: {slot.bg_color1}; color: {slot.text_color};"
    except Exception:
        return ""
