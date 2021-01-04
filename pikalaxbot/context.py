import discord
from discord.ext import commands
import asyncio
from typing import *


__all__ = ('FakeContext', 'MyContext')


class FakeContext(NamedTuple):
    guild: Optional[discord.Guild]
    channel: discord.TextChannel
    message: Optional[discord.Message]
    author: Union[discord.Member, discord.User]
    command: Optional[commands.Command] = None


class MyContext(commands.Context):
    def __init__(self, **attrs):
        super().__init__(**attrs)
        self._message_history: set[int] = set()
        self._task = asyncio.current_task()

    async def send(self, content: Optional[str] = None, **kwargs):
        msg = await super().send(content, **kwargs)
        self.bot._ctx_cache[(self.channel.id, self.message.id)][1].add(msg.id)
        return msg

    async def reply(self, content: Optional[str] = None, **kwargs):
        msg = await super().reply(content, **kwargs)
        self.bot._ctx_cache[(self.channel.id, self.message.id)][1].add(msg.id)
        return msg

    def cancel(self, msg=None):
        self._task.cancel(msg)
