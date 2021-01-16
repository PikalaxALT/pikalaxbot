# PikalaxBOT - A Discord bot in discord.py
# Copyright (C) 2018-2021  PikalaxALT
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import discord
from discord.ext import commands
import asyncio
from typing import *
if TYPE_CHECKING:
    from .bot import PikalaxBOT


__all__ = ('FakeContext', 'MyContext')


class FakeContext(NamedTuple):
    guild: Optional[discord.Guild]
    channel: discord.TextChannel
    message: Optional[discord.Message]
    author: Union[discord.Member, discord.User]
    bot: 'PikalaxBOT'
    command: Optional[commands.Command] = None


class MyContext(commands.Context):
    def __init__(self, **attrs):
        super().__init__(**attrs)
        self._message_history: set[int] = set()
        self._task = asyncio.current_task()

    async def send(self, content: Optional[str] = None, **kwargs) -> discord.Message:
        msg = await super().send(content, **kwargs)
        self.bot._ctx_cache[(self.channel.id, self.message.id)][1].add(msg.id)
        return msg

    async def reply(self, content: Optional[str] = None, **kwargs) -> discord.Message:
        msg = await super().reply(content, **kwargs)
        self.bot._ctx_cache[(self.channel.id, self.message.id)][1].add(msg.id)
        return msg

    def cancel(self, msg=None):
        self._task.cancel(msg)
