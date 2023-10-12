# --------------------------------------------------------------------
# models.py
#
# Author: Lain Musgrove (lain.proliant@gmail.com)
# Date: Tuesday September 12, 2023
# --------------------------------------------------------------------

from datetime import datetime, timedelta

import shortuuid
from mememo.config import Config
from django.utils import timezone
from django.contrib.auth.models import User
from django.db import models

# --------------------------------------------------------------------
THIRD_PARTY_AUTH_EXPIRY_DAYS = 120
SERVICE_GRANT_EXPIRY_DAYS = 365
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
class SystemPerms(models.Model):
    class Meta:
        managed = False
        default_permissions = ()
        permissions = (
            (
                "third_party_gateway",
                "third_party_gateway",
            ),
            ("gatekeeper", "gatekeeper"),
        )


# --------------------------------------------------------------------
class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


# --------------------------------------------------------------------
class ServiceGrant(TimestampedModel):
    service_name = models.CharField(max_length=128)
    grant_name = models.CharField(max_length=128)

    class Meta:
        unique_together = ("service_name", "grant_name")

    @classmethod
    def join(cls, service_name: str, grant_name: str) -> str:
        result = ":".join([service_name, grant_name])
        cls.split(result)  # Assert no extra ':' seps snuck in by error.
        return result

    @classmethod
    def split(cls, grant_code: str) -> tuple[str, str]:
        service_name, grant_name = grant_code.split(":")
        return (service_name, grant_name)

    @classmethod
    def by_code(cls, grant_code: str) -> "ServiceGrant":
        service_name, grant_name = cls.split(grant_code)
        return ServiceGrant.objects.get(
            service_name=service_name, grant_name=grant_name
        )

    @classmethod
    def by_user(cls, user: User) -> set[str]:
        results = set()
        for assignment in ServiceGrantAssignment.objects.filter(
            user=user
        ):
            results.add(assignment.grant.to_code())
        return results

    def to_code(self) -> str:
        return f"{self.service_name}:{self.grant_name}"


# --------------------------------------------------------------------
class ServiceGrantAssignment(TimestampedModel):
    grant = models.ForeignKey(ServiceGrant, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    expiry_dt = models.DateTimeField()

    def save(self, *args, **kwargs):
        if not self.pk:
            self.expiry_dt = timezone.now() + timedelta(days=SERVICE_GRANT_EXPIRY_DAYS)
        super().save(*args, **kwargs)


# --------------------------------------------------------------------
class Topic(TimestampedModel):
    id = id_field()
    cmd = models.TextField()
    env = models.JSONField(default=dict)
    service_name = models.CharField(max_length=128)
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
    user = models.ForeignKey(
        User, default=None, on_delete=models.CASCADE, unique=False, null=True
    )


# --------------------------------------------------------------------
class Subscription(TimestampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("user", "topic")
