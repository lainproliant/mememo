# --------------------------------------------------------------------
# models.py
#
# Author: Lain Musgrove (lain.proliant@gmail.com)
# Date: Tuesday September 12, 2023
# --------------------------------------------------------------------

from datetime import datetime

import shortuuid
from django.db import models
from django.contrib.auth.models import User

# --------------------------------------------------------------------
DEFAULT_TOPIC_RUN_FREQ_MIN = 5
SHORTUUID_LEN = 8
USERNAME_LEN = 32


# --------------------------------------------------------------------
def new_id() -> str:
    return shortuuid.random(length=8)


# --------------------------------------------------------------------
def username_field() -> models.CharField:
    return models.CharField(max_length=USERNAME_LEN)


# --------------------------------------------------------------------
class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


# --------------------------------------------------------------------
class Topic(TimestampedModel):
    id = models.CharField(
        primary_key=True, default=new_id, editable=False, max_length=SHORTUUID_LEN
    )
    cmd = models.TextField()
    env = models.JSONField(default=dict)
    last_run_dt = models.DateTimeField(default=datetime.min)
    next_run_dt = models.DateTimeField(default=datetime.min)
    run_freq_minutes = models.IntegerField(default=DEFAULT_TOPIC_RUN_FREQ_MIN)


# --------------------------------------------------------------------
class Subscription(TimestampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE)
