# --------------------------------------------------------------------
# agent.py
#
# Author: Lain Musgrove (lain.proliant@gmail.com)
# Date: Wednesday September 13, 2023
# --------------------------------------------------------------------

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from models import ThirdPartyAuthentication

from bivalve.agent import BivalveAgent
from bivalve.aio import Connection
from bivalve.logging import LogManager
from bivalve.constants import Permissions
from django.contrib.auth import authenticate
from django.contrib.auth.models import User

# --------------------------------------------------------------------
SESSION_TIMEOUT = timedelta(minutes=5)

log = LogManager().get(__name__)


# --------------------------------------------------------------------
@dataclass
class Session:
    conn: Connection
    expiry_dt: datetime = field(
        default_factory=lambda: datetime.now() + SESSION_TIMEOUT
    )
    user: Optional[User] = None


# --------------------------------------------------------------------
def authenticated(f):
    def wrapper(self: "MememoAgent", conn: Connection, *argv):
        session = self.sessions.get(conn.id)
        if not session or not session.user:
            raise RuntimeError("Not authenticated.")

        if session.user.has_perm(Permissions.THIRD_PARTY_GATEWAY):
            # This is a third party gateway user, representing a Discord or Slack agent.
            third_party_auth = ThirdPartyAuthentication.objects.filter(identity=identity).first()

            if third_party_auth is None or third_party_auth.user is None:
                raise RuntimeError("Third-party identity not authenticated.")

            if datetime.now() >= third_party_auth.expiry_dt:
                raise RuntimeError("Third-party identity authentication has expired, please re-authenticate.")

            user = third_party_auth.user

        else:
            # TODO: This is a direct user connection.


        if third_party_auth is None or third_party_auth.user is None:
            raise RuntimeError("Third-party identity not authenticated.")

        if datetime.now() >= third_party_auth.expiry_dt:
            raise RuntimeError("Third-party identity authentication has expired, please re-authenticate.")

        return f(session, *args)

    return wrapper


# --------------------------------------------------------------------
class MememoAgent(BivalveAgent):
    def __init__(self, path: Path):
        super().__init__()
        self.sessions: dict[Connection.ID, Session] = {}
        self.path = path

    async def run(self):
        try:
            await self.serve(path=self.path)
        except Exception:
            log.exception("Failed to start server.")
            self.shutdown()

        await super().run()

    def on_connect(self, conn: Connection):
        self.sessions[conn.id] = Session(conn)

    def on_client_disconnect(self, conn: Connection):
        del self.sessions[conn.id]

    def _identify(self, identity: str) -> Optional[User]:
        return ThirdPartyAuthentication.objects.filter(identity=identity).first()

    def fn_authenticate(
        self,
        conn: Connection,
        identity: str,
        alias: str,
        challenge: Optional[str] = None,
    ):
        session = self.sessions[conn.id]

        session.user = authenticate(username, password)
        if session.user:
            return "OK"
        else:
            return "FAIL"

    @auth_fn
    def fn_check(self, identity, alias, *argv):
        return "OK"
