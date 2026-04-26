from django.db import migrations


def seed_initial_staff(apps, schema_editor):
    Staff = apps.get_model("scheduling", "Staff")
    names = ["Moe", "Sufian", "Hasan", "Imran", "Shemul", "Nayem"]

    for name in names:
        if not Staff.objects.filter(name__iexact=name).exists():
            Staff.objects.create(name=name)


class Migration(migrations.Migration):

    dependencies = [
        ("scheduling", "0003_alter_scheduletheme_created_at_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_initial_staff, migrations.RunPython.noop),
    ]

