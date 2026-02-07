from django.db import migrations


def seed(apps, schema_editor):
    Slot = apps.get_model("scheduling", "Slot")
    ScheduleTheme = apps.get_model("scheduling", "ScheduleTheme")

    ScheduleTheme.objects.get_or_create(
        id=1,
        defaults={
            "header_bg_type": "gradient",
            "header_bg_color1": "#0f172a",
            "header_bg_color2": "#2563eb",
            "header_text_color": "#ffffff",
            "table_header_bg": "#f3f4f6",
            "table_header_text": "#111827",
            "weekend_bg": "#fafafa",
            "blocked_bg": "#fda4af",
        },
    )

    rows = [
        # exclusive
        ("off_day", "Off Day", 10, False, "solid", "#fde68a", "#fde68a", "#111827", "7-11"),
        ("pt", "PT", 20, True, "solid", "#fde68a", "#fde68a", "#111827", "7-11"),
        ("ph_al", "PH*/AL@", 30, False, "solid", "#bae6fd", "#bae6fd", "#111827", "7-11"),

        # times
        ("10am", "10am", 40, False, "solid", "#ffffff", "#ffffff", "#111827", "7-11"),
        ("11am", "11am", 50, False, "solid", "#ffffff", "#ffffff", "#111827", "7-11"),
        ("12pm", "12pm", 60, False, "solid", "#ffffff", "#ffffff", "#111827", "7-11"),
        ("1pm", "1pm", 70, False, "solid", "#ffffff", "#ffffff", "#111827", "7-11"),
        ("2pm", "2pm", 80, False, "solid", "#ffffff", "#ffffff", "#111827", "7-11"),
        ("3pm", "3pm", 90, False, "solid", "#ffffff", "#ffffff", "#111827", "7-11"),
        ("4pm", "4pm", 100, False, "solid", "#ffffff", "#ffffff", "#111827", "7-11"),
    ]

    for key, label, order, allow_block, bg_type, c1, c2, tc, pt_default in rows:
        Slot.objects.update_or_create(
            key=key,
            defaults={
                "label": label,
                "sort_order": order,
                "allow_block": allow_block,
                "bg_type": bg_type,
                "bg_color1": c1,
                "bg_color2": c2,
                "text_color": tc,
                "pt_default_time": pt_default,
            },
        )


def unseed(apps, schema_editor):
    Slot = apps.get_model("scheduling", "Slot")
    ScheduleTheme = apps.get_model("scheduling", "ScheduleTheme")
    Slot.objects.all().delete()
    ScheduleTheme.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("scheduling", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
