# --------------------------------------------------------------------
# models.py
#
# Author: Lain Musgrove (lain.proliant@gmail.com)
# Date: Tuesday September 12, 2023
# --------------------------------------------------------------------

import hashlib
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

import shortuuid
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from mememo.config import Config

# --------------------------------------------------------------------
AUTH_TOKEN_HASH_ROUNDS = 500
DEFAULT_TOPIC_RUN_FREQ_MIN = 5
SHORTUUID_LEN = 8
CHALLENGE_LEN = 128
USERNAME_LEN = 32
AUTH_TOKEN_LENGTH = 72


# --------------------------------------------------------------------
def new_id() -> str:
    return shortuuid.random(length=SHORTUUID_LEN)


# --------------------------------------------------------------------
def new_quadcode() -> str:
    prev_alpha = shortuuid.get_alphabet()
    shortuuid.set_alphabet("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    quadcode = shortuuid.random(4)
    shortuuid.set_alphabet(prev_alpha)
    return quadcode


# --------------------------------------------------------------------
def new_challenge() -> str:
    return shortuuid.random(length=CHALLENGE_LEN)


# --------------------------------------------------------------------
def new_auth_token() -> str:
    return shortuuid.random(length=AUTH_TOKEN_LENGTH)


# --------------------------------------------------------------------
def hash_auth_token(auth_token: str) -> str:
    token_bytes = auth_token.encode("utf-8")
    h = hashlib.new("sha512")
    for _ in range(AUTH_TOKEN_HASH_ROUNDS):
        h.update(token_bytes)
        token_bytes = h.digest()
    return h.hexdigest()


# --------------------------------------------------------------------
def id_field():
    return models.CharField(
        primary_key=True,
        default=new_id,
        editable=False,
        max_length=SHORTUUID_LEN,
    )


# --------------------------------------------------------------------
def quadcode_field():
    return models.CharField(
        unique=True, editable=False, max_length=4, default=new_quadcode
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

    def __str__(self) -> str:
        return f"{self.service_name}:{self.grant_name}"

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
        for assignment in ServiceGrantAssignment.objects.filter(user=user):
            results.add(assignment.grant.to_code())
        return results

    def to_code(self) -> str:
        return f"{self.service_name}:{self.grant_name}"


# --------------------------------------------------------------------
class ServiceGrantAssignment(TimestampedModel):
    grant = models.ForeignKey(ServiceGrant, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    expiry_dt = models.DateTimeField()

    def __str__(self) -> str:
        return f"{self.user.username} -> {self.grant}"

    def save(self, *args, **kwargs):
        if not self.pk:
            self.expiry_dt = (
                timezone.now() + Config.get().system.get_service_grant_expiry()
            )
        super().save(*args, **kwargs)


# --------------------------------------------------------------------
class AuthToken(TimestampedModel):
    id = models.CharField(primary_key=True, max_length=256)
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    expiry_dt = models.DateTimeField()

    def __str__(self) -> str:
        return f"{self.user.username} until {self.expiry_dt.isoformat()}"

    @classmethod
    def new(self, user: User) -> tuple[str, "AuthToken"]:
        plaintext_token = new_auth_token()
        hashed_token = hash_auth_token(plaintext_token)
        token = AuthToken(id=hashed_token, user=user)
        token.save()
        return plaintext_token, token

    @classmethod
    def resolve(self, plaintext_token: str) -> Optional[User]:
        hashed_token = hash_auth_token(plaintext_token)
        token = AuthToken.objects.filter(id=hashed_token).first()
        if token is None:
            return None
        return token.user

    def save(self, *args, **kwargs):
        if not self.expiry_dt:
            self.expiry_dt = timezone.now() + Config.get().auth3p.get_expiry()
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

    def __str__(self) -> str:
        return f"{self.service_name} {self.id}"


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

    def __str__(self) -> str:
        return f"{self.identity} ({self.alias}) until {self.expiry_dt.isoformat()}"


# --------------------------------------------------------------------
class Subscription(TimestampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE)

    def __str__(self) -> str:
        return f"{self.user.username} -> {self.topic}"

    class Meta:
        unique_together = ("user", "topic")


# --------------------------------------------------------------------
@dataclass
class CachedSetting:
    key: str
    value: str
    expiry_dt: datetime = field(default_factory=datetime.now)


# --------------------------------------------------------------------
class SettingsCache:
    def __init__(self):
        self.cache: dict[str, CachedSetting] = {}

    @classmethod
    def get_cache(cls) -> "SettingsCache":
        if cls.INSTANCE is None:
            cls.INSTANCE = SettingsCache()
        return cls.INSTANCE

    def get(self, key: str) -> str | None:
        if key in self.cache:
            setting = self.cache[key]
            now = datetime.now()
            if now > setting.expiry_dt:
                del self.cache[key]
            else:
                return setting.value
        return None

    def put(self, key: str, value: str) -> CachedSetting:
        setting = CachedSetting(
            key, value, datetime.now() + Config.get().system.get_settings_expiry()
        )
        self.cache[key] = setting
        return setting


# --------------------------------------------------------------------
class Setting(TimestampedModel):
    key = models.TextField(primary_key=True)
    value = models.TextField()

    @classmethod
    def get(self, key: str, default: str | None = None, type=str) -> str | None:
        cache = SettingsCache.get_cache()
        setting = cache.get(key, default, type)
        if setting is None:
            setting = Settings.objects.filter(key=key).first()
            if setting is None:
                if default is None:
                    raise ValueError(
                        f"Missing Mememo setting with no default value: {key}"
                    )
                setting = cache.put(key, default)
            else:
                setting = cache.put(setting.key, setting.value)

        return type(setting.value)
