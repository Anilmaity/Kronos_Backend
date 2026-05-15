from __future__ import absolute_import, unicode_literals

import os

from celery import Celery
from celery.schedules import crontab, timedelta

# set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Kronos_Backend.settings")

app = Celery("Kronos_Backend")

app.conf.enable_utc = False

app.conf.update(timezone="Asia/Kolkata")
app.config_from_object("django.conf:settings", namespace="CELERY")

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()
