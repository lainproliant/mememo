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
from typing import Optional

from mememo.domain import Topic, UserInfo

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

CREATE_USER_INFO_TABLE = """
create table user_info (
    id integer not null unique,
    username text not null
)
"""

TABLES: dict[str, str] = {
    "topics": CREATE_TOPICS_TABLE,
    "subscriptions": CREATE_SUBSCRIPTIONS_TABLE,
    "user_info": CREATE_USER_INFO_TABLE,
}

# --------------------------------------------------------------------
class TopicDAO:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def _row_to_obj(self, row) -> Topic:
        return Topic(*row)

    def list_names(self) -> list[str]:
        cur = self.conn.cursor()
        topics = sorted(cur.execute("select name from topics").fetchall())
        cur.close()
        return topics

    def list(self) -> list[Topic]:
        cur = self.conn.cursor()
        results = cur.execute("select name, script_path, last_updated_timestamp, update_freq_minutes, id from topics").fetchall()
        return [self._row_to_obj(row) for row in results]

    def create(self, topic: Topic) -> Topic:
        cur = self.conn.cursor()
        try:
            cur.execute(
                "insert into topics (name, script_path, update_freq_minutes) values (?, ?, ?)",
                (topic.name, topic.script_path, topic.update_freq_minutes),
            )
            assert cur.lastrowid is not None
            self.conn.commit()
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
            self.conn.commit()

        finally:
            cur.close()


# --------------------------------------------------------------------
class UserDAO:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def save(self, info: UserInfo):
        cur = self.conn.cursor()
        try:
            if self.find_by_id(info.id) is not None:
                cur.execute(
                    "update user_info set username = ? where id = ?",
                    (info.username, info.id),
                )
            else:
                cur.execute(
                    "insert into user_info (id, username) values (?, ?)",
                    (info.id, info.username),
                )

            assert cur.rowcount == 1
            self.conn.commit()

        finally:
            cur.close()

    def find_by_name(self, name: str) -> Optional[UserInfo]:
        cur = self.conn.cursor()
        try:
            result = cur.execute(
                "select id from user_info where username = ?", (name,)
            ).fetchone()
            return UserInfo(result, name) if result is not None else None

        finally:
            cur.close()

    def find_by_id(self, id: int) -> Optional[UserInfo]:
        cur = self.conn.cursor()
        try:
            result = cur.execute(
                "select username from user_info where id = ?", (id,)
            ).fetchone()
            return UserInfo(id, result) if result is not None else None

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
