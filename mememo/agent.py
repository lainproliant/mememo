# --------------------------------------------------------------------
# agent.py
#
# Author: Lain Musgrove (lain.proliant@gmail.com)
# Date: Wednesday September 13, 2023
# --------------------------------------------------------------------

import signal

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from bivalve.agent import BivalveAgent
from bivalve.aio import Connection
from bivalve.logging import LogManager
from django.contrib.auth import authenticate
from django.contrib.auth.models import User

# --------------------------------------------------------------------
SESSION_TIMEOUT = timedelta(minutes=5)

log = LogManager().get(__name__)
LogManager().setup()


# --------------------------------------------------------------------
@dataclass
class Session:
    conn: Connection
    expiry_dt: datetime = field(
        default_factory=lambda: datetime.now() + SESSION_TIMEOUT
    )
    user: Optional[User] = None
    echo = True


# --------------------------------------------------------------------
def auth_fn(f):
    def wrapper(self: "MememoAgent", conn: Connection, *args):
        now = datetime.now()
        if conn.id not in self.sessions:
            raise RuntimeError("Not authenticated.")

        session = self.sessions[conn.id]
        if now > session.expiry_dt:
            raise RuntimeError("Session expired.")

        return f(session, *args)

    return wrapper


# --------------------------------------------------------------------
class MememoAgent(BivalveAgent):
    def __init__(self, path: Path):
        super().__init__()
        self.sessions: dict[Connection.ID, Session] = {}
        self.path = path

    def ctrlc_handler(self, *_):
        log.critical("Ctrl+C received.")
        self.shutdown()

    async def run(self):
        signal.signal(signal.SIGINT, self.ctrlc_handler)
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

    def fn_authenticate(self, conn: Connection, username: str, password: str):
        session = self.sessions[conn.id]
        session.user = authenticate(username, password)
        if session.user:
            return "OK"
        else:
            return "FAIL"

    @auth_fn
    def fn_check(self, session: Session):
        return "OK"
