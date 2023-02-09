# --------------------------------------------------------------------
# db.py
#
# Author: Lain Musgrove (lain.proliant@gmail.com)
# Date: Wednesday February 8, 2023
#
# Distributed under terms of the MIT license.
# --------------------------------------------------------------------

import os
import sqlite3

from mememo.domain import Topic

# --------------------------------------------------------------------
CREATE_TOPICS_TABLE = """
create table topics (
    id integer not null primary key,
    name text not null unique,
    script_path text not null,
    update_freq_minutes integer not null,
    last_updated_timestamp timestamp
)
"""

CREATE_SUBSCRIPTIONS_TABLE = """
create table subscriptions (
    id integer not null primary key,
    user_id text not null
)
"""

TABLES: dict[str, str] = {
    "topics": CREATE_TOPICS_TABLE,
    "subscriptions": CREATE_SUBSCRIPTIONS_TABLE,
}

# --------------------------------------------------------------------
class TopicDAO:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def list_names(self) -> list[str]:
        cur = self.conn.cursor()
        topics = sorted(cur.execute("select name from topics").fetchall())
        cur.close()
        return topics

    def create(self, topic: Topic) -> Topic:
        cur = self.conn.cursor()
        try:
            cur.execute(
                "insert into topics (name, script_path, update_freq_minutes) values (?, ?, ?)",
                (topic.name, topic.script_path, topic.update_freq_minutes),
            )
            assert cur.lastrowid is not None
            topic.id = cur.lastrowid
            return topic

        finally:
            cur.close()

    def save(self, topic: Topic):
        cur = self.conn.cursor()
        try:
            cur.execute(
                "update topics set name = ?, script_path = ?, update_freq_minutes = ?, last_updated_timestamp = ? where id = ?",
                (
                    topic.name,
                    topic.script_path,
                    topic.update_freq_minutes,
                    topic.last_updated_timestamp,
                    topic.id,
                ),
            )
            assert cur.rowcount == 1

        finally:
            cur.close()


# --------------------------------------------------------------------
class DAOFactory:
    def topics(self) -> TopicDAO:
        raise NotImplementedError()


# --------------------------------------------------------------------
class SQLiteDAOFactory(DAOFactory):
    def __init__(self, db_filename):
        if not os.path.exists(db_filename):
            print("DB file doesn't exist, creating it...")
        self.conn = sqlite3.connect(db_filename)

        for table, create_ddl in TABLES.items():
            if not self._table_exists(table):
                print(f"Creating {table} table...")
                self.conn.execute(create_ddl)

    def _table_exists(self, name: str):
        cur = self.conn.cursor()
        matching_tables = cur.execute(
            "select name from sqlite_master where type='table' and name=?", (name,)
        ).fetchall()
        cur.close()
        return len(matching_tables) > 0

    def topics(self) -> TopicDAO:
        return TopicDAO(self.conn)
