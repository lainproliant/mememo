# --------------------------------------------------------------------
# models.py
#
# Author: Lain Musgrove (lain.proliant@gmail.com)
# Date: Tuesday September 12, 2023
# --------------------------------------------------------------------

from datetime import datetime, timedelta

import shortuuid
from django.contrib.auth.models import User
from django.db import models

# --------------------------------------------------------------------
THIRD_PARTY_AUTH_EXPIRY_DAYS = 120
DEFAULT_TOPIC_RUN_FREQ_MIN = 5
RANDOM_PW_LEN = 32
SHORTUUID_LEN = 8
CHALLENGE_LEN = 128
USERNAME_LEN = 32


# --------------------------------------------------------------------
def new_id() -> str:
    return shortuuid.random(length=SHORTUUID_LEN)


# --------------------------------------------------------------------
def new_challenge() -> str:
    return shortuuid.random(length=CHALLENGE_LEN)


# --------------------------------------------------------------------
def new_random_pw() -> str:
    return shortuuid.random(length=RANDOM_PW_LEN)


# --------------------------------------------------------------------
def id_field():
    return models.CharField(
        primary_key=True,
        default=new_id,
        editable=False,
        max_length=SHORTUUID_LEN,
    )


# --------------------------------------------------------------------
def challenge_field():
    return models.CharField(
        default=new_challenge, editable=True, max_length=CHALLENGE_LEN
    )


# --------------------------------------------------------------------
def username_field() -> models.CharField:
    return models.CharField(max_length=USERNAME_LEN)


# --------------------------------------------------------------------
class MememoPermissions(models.Model):
    class Meta:
        managed = False
        default_permissions = ()
        permissions = (
            (
                "third_party_gateway",
                "User can act as a third-party authentication gateway.",
            ),
        )


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
    challenge = challenge_field()
    identity = models.TextField(db_index=True, unique=True)
    alias = models.CharField(max_length=150)
    user = models.ForeignKey(User, default=None, on_delete=models.CASCADE, unique=False, null=True)


# --------------------------------------------------------------------
class Subscription(TimestampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE)
