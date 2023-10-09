# --------------------------------------------------------------------
# auth.py
#
# Author: Lain Musgrove (lain.proliant@gmail.com)
# Date: Monday September 18, 2023
# --------------------------------------------------------------------

import functools
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Optional, Union

from asgiref.sync import sync_to_async
from bivalve.aio import Connection
from django.utils import timezone
from django.contrib.auth import (
    authenticate as dj_authenticate,
)
from django.contrib.auth.models import User

from mememo.constants import Permissions
from mememo.models import ThirdPartyAuthentication
from mememo.util import django_sync

# --------------------------------------------------------------------
SESSION_TIMEOUT = timedelta(minutes=5)
AUTH3P_CHALLENGE_EXPIRY = timedelta(hours=1)
AUTH3P_EXPIRY = timedelta(days=90)


# --------------------------------------------------------------------
@dataclass
class Session:
    conn: Connection
    expiry_dt: datetime = field(
        default_factory=lambda: timezone.now() + SESSION_TIMEOUT
    )
    user: Optional[User] = None


# --------------------------------------------------------------------
def create_auth3p(identity: str, alias: str) -> ThirdPartyAuthentication:
    """
    Makes a new third-party authentication, replacing any previous one
    for the given identity.
    """

    ThirdPartyAuthentication.objects.filter(identity=identity).delete()
    auth3p = ThirdPartyAuthentication.objects.create(
        identity=identity,
        alias=alias,
        expiry_dt=timezone.now() + AUTH3P_CHALLENGE_EXPIRY,
    )
    auth3p.save()
    return auth3p


# --------------------------------------------------------------------
def auth(f_or_perm: Union[str, Callable], *perms: str):
    def decorator(perms: list[str], f: Callable):
        @functools.wraps(f)
        @django_sync
        def wrapper(self: Any, conn: Connection, *argv):
            session = self.sessions.get(conn.id)
            if not session or not session.user:
                raise RuntimeError("Not authenticated.")

            if session.user.has_perm(Permissions.THIRD_PARTY_GATEWAY):
                # This is a third party gateway user, representing a
                # Discord or Slack agent.  We want to authenticate the
                # third party user.
                identity, alias, *real_argv = argv
                third_party_auth = ThirdPartyAuthentication.objects.filter(
                    identity=identity
                ).first()

                if third_party_auth is None or third_party_auth.user is None:
                    raise RuntimeError("Third-party identity not authenticated yet.")

                if timezone.now() >= third_party_auth.expiry_dt:
                    raise RuntimeError(
                        "Third-party identity authentication has expired, please re-authenticate."
                    )

                user = third_party_auth.user

            else:
                user = session.user
                real_argv = [*argv]

            if perms and not user.has_perms(perms):
                raise RuntimeError("Not permitted.")

            return f(self, user, *real_argv)

        return wrapper

    if isinstance(f_or_perm, str):
        return functools.partial(decorator, [f_or_perm, *perms])
    return decorator([], f_or_perm)


# --------------------------------------------------------------------
async def authenticate(**kwargs) -> Optional[User]:
    return await sync_to_async(dj_authenticate)(**kwargs)


# --------------------------------------------------------------------
async def has_perms(user: User, *perms):
    return await sync_to_async(user.has_perms)(perms)
