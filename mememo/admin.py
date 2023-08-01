# --------------------------------------------------------------------
# admin.py
#
# Author: Lain Musgrove (lain.proliant@gmail.com)
# Date: Wednesday February 8, 2023
#
# Distributed under terms of the MIT license.
# --------------------------------------------------------------------

import os
from dataclasses import dataclass

from bivalve.agent import BivalveAgent
from bivalve.aio import Connection
from bivalve.logging import LogManager

from mememo.db import DAOFactory
from mememo.domain import Topic

# --------------------------------------------------------------------
log = LogManager().get(__name__)


# --------------------------------------------------------------------
@dataclass
class Session:
    conn: Connection
    echo = True


# --------------------------------------------------------------------
class AdminServer(BivalveAgent):
    def __init__(self, host: str, port: str, dao: DAOFactory):
        super().__init__()
        self.host = host
        self.port = port
        self.sessions: dict[Connection.ID, Session] = {}

    async def run(self):
        try:
            await self.serve(self.host, self.port)
        except Exception:
            log.exception("Failed to start server.")
            self.shutdown()

        await super().run()

    def on_connect(self, conn: Connection):
        self.sessions[conn.id] = Session(conn)

    def on_client_disconnect(self, conn: Connection):
        del self.sessions[conn.id]

    async def cmd_create_topic(
        self, conn: Connection, call_id, topic_name, script_path
    ):
        if topic_name in self.dao.topics().list_names():
            raise ValueError("Topic already exists.")
        if not os.path.exists(script_path):
            raise ValueError("Script path does not exist.")
        if not os.access(script_path, os.X_OK):
            raise ValueError("Script path is not executable.")

        topic = Topic(topic_name, os.path.abspath(script_path))
        try:
            self.dao.topics().create(topic)
            conn.send("return", call_id, 0, f"Created topic `{topic}`.")
        except Exception as e:
            msg = f"Failed to create topic {topic}."
            log.exception(msg)
            conn.send("return", call_id, 1, msg, str(e))

    def cmd_quit(self, conn: Connection, call_id):
        self.disconnect(conn)

    def cmd_list_topics(self, conn: Connection, call_id):
        topics = self.dao.topics().list_names()
        conn.send("return", call_id, 0, *topics)
