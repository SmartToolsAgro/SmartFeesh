"""Celery application: background jobs such as PDF generation (D-071). Redis is the broker."""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("frutti")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
