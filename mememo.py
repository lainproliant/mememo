# --------------------------------------------------------------------
# mememo.py
#
# Author: Lain Musgrove (lain.proliant@gmail.com)
# Date: Tuesday January 17, 2023
#
# Distributed under terms of the MIT license.
# --------------------------------------------------------------------

import os
import sqlite3
import shlex
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import discord
from dotenv import load_dotenv
from xeno import Injector, provide, singleton

# --------------------------------------------------------------------
CREATE_TOPICS_TABLE = """
create table topics (
    id integer not null primary key,
    name text not null,
    script_path text not null,
    update_freq_minutes integer not null default 30,
    last_updated_timestamp timestamp
)
"""

CREATE_SUBSCRIPTION_TABLE = """
create table subscriptions (
    id integer not null primary key,
    user_id text not null
)
"""

# --------------------------------------------------------------------
def env_require(name: str) -> str:
    value = os.getenv(name)
    if value is None:
        raise ValueError(f"Missing environment variable '{name}'.")
    return value


# --------------------------------------------------------------------
def db_table_exists(conn: sqlite3.Connection, name: str) -> bool:
    cur = conn.cursor()
    matching_tables = cur.execute(
        "select name from sqlite_master where type='table' and name=?", (name,)
    ).fetchall()
    cur.close()
    return len(matching_tables) > 0


# --------------------------------------------------------------------
def db_init(db_filename: str) -> sqlite3.Connection:
    if not os.path.exists(db_filename):
        print("DB file doesn't exist, creating it...")
    conn = sqlite3.connect(db_filename)
    if not db_table_exists(conn, "topics"):
        print("Creating topics table...")
        conn.execute(CREATE_TOPICS_TABLE)
        print("Creating subscriptions table...")
    if not db_table_exists(conn, "subscriptions"):
        conn.execute(CREATE_SUBSCRIPTION_TABLE)
    return conn


# --------------------------------------------------------------------
def db_get_topics(conn: sqlite3.Connection) -> list[str]:
    cur = conn.cursor()
    topics = sorted(cur.execute("select name from topics").fetchall())
    cur.close()
    return topics


# --------------------------------------------------------------------
class MememoBotClient(discord.Client):
    def __init__(self, db_filename: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.conn = db_init(db_filename)
        self.commands: dict[str, Any] = {}
        self._create_command_map()

    def __del__(self):
        super().__del__()
        self.conn.close()

    def _create_command_map(self):
        self.commands["subscribe"] = self.cmd_subscribe
        self.commands["unsubscribe"] = self.cmd_unsubscribe
        self.commands["topics"] = self.cmd_topics

    async def cmd_topics(self, message, *args):
        topics = db_get_topics(self.conn)

        if not topics:
            await message.channel.send(
                f"Hi {message.author.name}!  No topics are available to subcribe to yet."
            )
            return

        await message.channel.send(
            f"Hi {message.author.name}!  These are the available topics: {topics}"
        )

    async def cmd_subscribe(self, message, *args):
        await message.channel.send(
            f"{message.author.name}, I would subscribe you to topic {args[0]}, but I don't know how to do that yet."
        )

    async def cmd_unsubscribe(self, message, *args):
        pass

    async def on_ready(self):
        print(f"{self.user} has connected to Discord!")

    async def on_message(self, message):
        if message.author == self.user:
            return

        if message.content.startswith(f"<@{self.user.id}>"):
            argv = shlex.split(message.content)[1:]
            try:
                cmd = argv[0]
                if cmd not in self.commands:
                    raise ValueError(f"I don't understand '{cmd}'.")
                await self.commands[cmd](message, *argv[1:])

            except Exception as e:
                await message.channel.send(f"I'm sorry, {e}")


# --------------------------------------------------------------------
def run_discord_client(db_filename: str, discord_access_token: str):
    intents = discord.Intents(messages=True)
    client = MememoBotClient(db_filename, intents=intents)
    client.run(discord_access_token)


# --------------------------------------------------------------------
class Module:
    @singleton
    def dotenv(self):
        load_dotenv()

    @singleton
    def db_filename(self, dotenv) -> str:
        return env_require("MEMEMO_DB")

    @provide
    def discord_access_token(self, dotenv):
        return env_require("DISCORD_TOKEN")

    @provide
    def discord_client(self, db_connection):
        intents = discord.Intents(messages=True)
        return MememoBotClient(db_connection, intents=intents)

    @provide
    def execution(self, db_filename, discord_access_token):
        with ThreadPoolExecutor(max_workers=2) as executor:
            executor.submit(lambda: run_discord_client(db_filename, discord_access_token))


# --------------------------------------------------------------------
def main():
    injector = Injector(Module())
    injector.require("execution")


# --------------------------------------------------------------------
if __name__ == "__main__":
    main()
