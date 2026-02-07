from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Staff",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=80, unique=True)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("updated_at", models.DateTimeField(default=django.utils.timezone.now)),
            ],
        ),
        migrations.CreateModel(
            name="Slot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.SlugField(max_length=40, unique=True)),
                ("label", models.CharField(max_length=40)),
                ("sort_order", models.IntegerField(default=0)),
                ("allow_block", models.BooleanField(default=False)),
                ("bg_type", models.CharField(choices=[("solid", "Solid"), ("gradient", "Gradient")], default="solid", max_length=10)),
                ("bg_color1", models.CharField(default="#ffffff", max_length=20)),
                ("bg_color2", models.CharField(default="#ffffff", max_length=20)),
                ("text_color", models.CharField(default="#111827", max_length=20)),
                ("pt_default_time", models.CharField(blank=True, default="7-11", max_length=20)),
            ],
        ),
        migrations.CreateModel(
            name="ScheduleTheme",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("header_bg_type", models.CharField(choices=[("solid", "Solid"), ("gradient", "Gradient")], default="gradient", max_length=10)),
                ("header_bg_color1", models.CharField(default="#0f172a", max_length=20)),
                ("header_bg_color2", models.CharField(default="#2563eb", max_length=20)),
                ("header_text_color", models.CharField(default="#ffffff", max_length=20)),
                ("table_header_bg", models.CharField(default="#f3f4f6", max_length=20)),
                ("table_header_text", models.CharField(default="#111827", max_length=20)),
                ("weekend_bg", models.CharField(default="#fafafa", max_length=20)),
                ("blocked_bg", models.CharField(default="#fda4af", max_length=20)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("updated_at", models.DateTimeField(default=django.utils.timezone.now)),
            ],
        ),
        migrations.CreateModel(
            name="ScheduleWeek",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("week_start", models.DateField(db_index=True, unique=True)),
                ("cells", models.JSONField(blank=True, default=dict)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("updated_at", models.DateTimeField(default=django.utils.timezone.now)),
            ],
        ),
    ]
