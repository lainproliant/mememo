# --------------------------------------------------------------------
# agent.py
#
# Author: Lain Musgrove (lain.proliant@gmail.com)
# Date: Wednesday September 13, 2023
# --------------------------------------------------------------------

from pathlib import Path
from typing import Optional

from bivalve.agent import BivalveAgent
from bivalve.aio import Connection
from bivalve.logging import LogManager
from django.contrib.auth.models import User

from mememo.auth import Session, auth, authenticate, create_auth3p
from mememo.constants import Permissions
from mememo.models import ThirdPartyAuthentication, new_random_pw
from mememo.util import django_sync

# --------------------------------------------------------------------
log = LogManager().get(__name__)


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

    async def fn_auth(self, conn: Connection, username: str, password: str):
        session = self.sessions[conn.id]
        session.user = await authenticate(username=username, password=password)
        if session.user is None:
            raise RuntimeError("Invalid credentials.")
        return f"Authenticated as {session.user.username}."

    @django_sync
    def fn_auth3p(
        self,
        conn: Connection,
        identity: str,
        alias: str,
        challenge: Optional[str] = None,
    ):
        session = self.sessions[conn.id]

        if session.user is None or not session.user.has_perm(Permissions.THIRD_PARTY_GATEWAY):
            raise RuntimeError(
                "Can't authenticate third-party users, this user is not a third party gateway."
            )

        if challenge is None:
            auth3p = create_auth3p(identity, alias)

            return "Ask the administrator for a challenge code, then send it back to me via `auth <challenge-code>`."

        else:
            auth3p = ThirdPartyAuthentication.objects.filter(identity=identity).first()
            if auth3p is None:
                raise RuntimeError("Not permitted.")

        if challenge != auth3p.challenge:
            raise RuntimeError("Challenge failed.")

        user = User.objects.filter(username=auth3p.alias).first()
        if user is None:
            user = User.objects.create(username=auth3p.alias, password=new_random_pw())
            user.save()

        auth3p.user = user
        auth3p.save()
        return f"You're authenticated, {user.username}."

    @auth
    def fn_hello(self, user: User, *argv):
        return f"Hello, {user.username}!"
