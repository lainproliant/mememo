# Generated by Django 4.2.5 on 2023-09-19 06:34

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import mememo.models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("mememo", "0002_alter_topic_env"),
    ]

    operations = [
        migrations.CreateModel(
            name="ThirdPartyAuthentication",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "id",
                    models.CharField(
                        default=mememo.models.new_id,
                        editable=False,
                        max_length=8,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("expiry_dt", models.DateTimeField()),
                (
                    "challenge",
                    models.CharField(
                        default=mememo.models.new_challenge, max_length=128
                    ),
                ),
                ("identity", models.TextField(db_index=True, unique=True)),
                ("alias", models.CharField(max_length=150)),
                (
                    "user",
                    models.ForeignKey(
                        default=None,
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
    ]
