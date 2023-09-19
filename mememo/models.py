# --------------------------------------------------------------------
# models.py
#
# Author: Lain Musgrove (lain.proliant@gmail.com)
# Date: Tuesday September 12, 2023
# --------------------------------------------------------------------

from datetime import datetime, timedelta

import shortuuid
from django.db import models
from django.contrib.auth.models import User

# --------------------------------------------------------------------
THIRD_PARTY_AUTH_EXPIRY_DAYS = 120
DEFAULT_TOPIC_RUN_FREQ_MIN = 5
SHORTUUID_LEN = 8
CHALLENGE_LEN = 128
USERNAME_LEN = 32


# --------------------------------------------------------------------
def new_id() -> str:
    return shortuuid.random(length=8)


# --------------------------------------------------------------------
def id_field(len=SHORTUUID_LEN) -> str:
    return models.CharField(
        primary_key=True, default=new_id, editable=False, max_length=len
    )


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
    id = id_field()
    cmd = models.TextField()
    env = models.JSONField(default=dict)
    last_run_dt = models.DateTimeField(default=datetime.min)
    next_run_dt = models.DateTimeField(default=datetime.min)
    run_freq_minutes = models.IntegerField(default=DEFAULT_TOPIC_RUN_FREQ_MIN)


# --------------------------------------------------------------------
class ThirdPartyAuthentication(TimestampedModel):
    id = id_field()
    expiry_dt = models.DateTimeField()
    challenge = id_field(CHALLENGE_LEN)
    identity = models.TextField(db_index=True, unique=True)
    alias = models.CharField(max_length=150)
    user = models.ForeignKey(User, default=None, on_delete=models.CASCADE, unique=False)


# --------------------------------------------------------------------
class Subscription(TimestampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE)
