# --------------------------------------------------------------------
# mememo.py
#
# Author: Lain Musgrove (lain.proliant@gmail.com)
# Date: Tuesday January 17, 2023
#
# Distributed under terms of the MIT license.
# --------------------------------------------------------------------

import inspect
import os
import shlex
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import partial
from pathlib import Path
from typing import Any

import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv
from xeno import SyncInjector, provide, singleton
from xeno.color import color

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

ADMIN_INTRO = """
--------------------------------------
Welcome to the Mememo admin interface.
--------------------------------------
"""

# --------------------------------------------------------------------
@dataclass
class Topic:
    id: int
    name: str
    script_path: Path
    update_freq_minutes: int
    last_updated_timestamp: datetime


# --------------------------------------------------------------------
@dataclass
class Subscription:
    topic_id: int
    user_id: int


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
    for table, create_ddl in TABLES.items():
        if not db_table_exists(conn, table):
            print(f"Creating {table} table...")
            conn.execute(create_ddl)

    return conn


# --------------------------------------------------------------------
def db_list_topics(conn: sqlite3.Connection) -> list[str]:
    cur = conn.cursor()
    topics = sorted(cur.execute("select name from topics").fetchall())
    cur.close()
    return topics


# --------------------------------------------------------------------
def get_prefixed_methods(prefix, obj):
    return [
        getattr(obj, name)
        for name in dir(obj)
        if name.startswith(prefix) and callable(getattr(obj, name))
    ]


# --------------------------------------------------------------------
class Commands:
    @staticmethod
    def get_prefixed_methods(prefix, obj):
        return [
            getattr(obj, name)
            for name in dir(obj)
            if name.startswith(prefix) and callable(getattr(obj, name))
        ]

    def __init__(self, obj, prefix="cmd_"):
        self.map: dict[str, Any] = {}
        self.prefix = prefix
        for method in Commands.get_prefixed_methods(self.prefix, obj):
            self.define(method)

    def define(self, f):
        self.map[f.__name__.removeprefix(self.prefix)] = f

    def get(self, name) -> Any:
        if name not in self.map:
            raise ValueError(f"Command `{name}` is not defined.")
        return self.map[name]

    def signatures(self):
        for key, value in self.map.items():
            yield (key, inspect.signature(value))


# --------------------------------------------------------------------
class AdminCommandInterface:
    def __init__(self, db_filename: str):
        self.conn = db_init(db_filename)
        self.commands = Commands(self)

    def cmd_create_topic(self, topic_name, script_path):
        if topic_name in db_list_topics(self.conn):
            raise ValueError("Topic already exists.")
        if not os.path.exists(script_path):
            raise ValueError("Script path does not exist.")
        if not os.access(script_path, os.X_OK):
            raise ValueError("Script path is not executable.")

    def cmd_quit(self):
        bye = partial(color, fg="white", render="dim")
        print(bye("Goodbye."))
        sys.exit(0)

    def cmd_help(self):
        cmd = partial(color, fg="green")
        param = partial(color, fg="cyan", render="dim")
        for key, signature in self.commands.signatures():
            print(f"{cmd(key)} {param(' '.join(signature.parameters))}")

    def run(self):
        prompt = partial(color, fg="yellow")
        intro = partial(color, fg="white", render="dim")
        error = partial(color, fg="red")
        print(intro(ADMIN_INTRO))
        while True:
            try:
                s = input(prompt("admin> "))
                if not s:
                    continue
                argv = shlex.split(s)
                self.commands.get(argv[0])(*argv[1:])

            except Exception as e:
                print(f"{error('ERROR')}: {e}")


# --------------------------------------------------------------------
class MememoBotClient(discord.Client):
    def __init__(self, db_filename: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.conn = db_init(db_filename)
        self.commands = Commands(self)

    def __del__(self):
        self.conn.close()

    async def respond(self, message, text):
        await message.channel.send(f"Hi {message.author.name}! " + text)

    async def cmd_topics(self, message, *args):
        topics = db_list_topics(self.conn)

        if not topics:
            await self.respond(message, "No topics are available to subscribe to yet.")
            return

        await self.respond(message, f"These are the available topics: {topics}")

    async def cmd_subscribe(self, message, topic):
        await self.respond(
            message,
            f"I would like to subscribe you to topic {topic}, but I don't know how to do that yet.",
        )

    async def cmd_unsubscribe(self, message, topic):
        await self.respond(message, "I don't know how to do that yet.")

    async def cmd_whoami(self, message):
        await self.respond(
            message, f"You are {message.author}, with id {message.author.id}"
        )

    async def on_ready(self):
        print(f"{self.user} has connected to Discord!")

    async def on_message(self, message):
        if message.author == self.user:
            return

        if self.user in message.mentions:
            argv = [x for x in shlex.split(message.content) if x != self.user.mention]
            try:
                await self.commands.get(argv[0])(message, *argv[1:])

            except Exception as e:
                await message.channel.send(f"I'm sorry, {e}")


# --------------------------------------------------------------------
class TopicRunner:
    def __init__(self, topic: Topic, last_updated: datetime = datetime.min):
        self.topic = topic

    def run(self):
        # TODO: Run and see if there's any output.
        pass


# --------------------------------------------------------------------
class TopicUpdateService(commands.Cog):
    def __init__(self, bot: discord.Client):
        self.bot = bot
        self.update_task.start()
        self.runners: dict[str, TopicRunner] = {}

    def cog_unload(self):
        self.update_task.cancel()

    @tasks.loop(minutes=5.0)
    async def update_task(self):
        async with self.bot.pool.acquire() as con:
            pass


# --------------------------------------------------------------------
class Module:
    @singleton
    def dotenv(self):
        load_dotenv()

    @provide
    def db_filename(self, dotenv):
        return env_require("MEMEMO_DB")

    @provide
    def access_token(self, dotenv):
        return env_require("DISCORD_TOKEN")

    @singleton
    def bot(self, db_filename, access_token):
        intents = discord.Intents(messages=True, message_content=True, typing=True)
        bot = MememoBotClient(db_filename, intents=intents)
        bot.run(access_token)

    @singleton
    def admin(self, db_filename):
        admin = AdminCommandInterface(db_filename)
        admin.run()


# --------------------------------------------------------------------
def main(argv):
    injector = SyncInjector(Module())

    if len(argv) > 0 and argv[0] == "admin":
        injector.require("admin")
    else:
        injector.require("bot")


# --------------------------------------------------------------------
if __name__ == "__main__":
    main(sys.argv[1:])
