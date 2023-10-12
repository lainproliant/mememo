# --------------------------------------------------------------------
# discord/utils.py
#
# Author: Lain Musgrove (lain.proliant@gmail.com)
# Date: Thursday October 12, 2023
# --------------------------------------------------------------------
import io
import re

from dataclasses import dataclass

from mememo.response import ResponseDigestor
from bivalve.logging import LogManager

import discord

# --------------------------------------------------------------------
log = LogManager().get(__name__)

# --------------------------------------------------------------------
@dataclass
class ResponseContext:
    client: discord.Client
    message: discord.Message


# --------------------------------------------------------------------
class DiscordResponseDigestor(ResponseDigestor[ResponseContext]):
    def digest_error(self, ctx: ResponseContext, content: list[str]) -> str:
        sb = io.StringIO()
        sb.write(":warning: Sorry, something went wrong.\n")
        sb.write("```\n")
        for line in content:
            sb.write(line + "\n")
        sb.write("```\n")
        return sb.getvalue()

    def _user_mention(self, ctx: ResponseContext, match: re.Match) -> str:
        username = match.group(1)
        try:
            user = ctx.message.guild.get_member_named(username)
            return user.mention
        except Exception:
            if username == ctx.message.author.name:
                return ctx.message.author.mention
            return f"<no user: {username}>"

    def _room_mention(self, ctx: ResponseContext, match: re.Match) -> str:
        roomname = match.group(1)
        try:
            room = discord.utils.get(ctx.message.guild.channels, name=roomname)
            return room.mention
        except Exception:
            log.exception()
            return f"<no room: {roomname}>"
