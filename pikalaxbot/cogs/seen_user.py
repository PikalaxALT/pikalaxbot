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

import datetime
import discord
from collections import defaultdict
from discord.ext import commands
import typing
from . import *
from humanize import naturaldelta
import re
import operator


class SeenUser(BaseCog):
    """Commands for tracking users' most recent activity."""

    MAX_LOOKBACK = datetime.timedelta(days=1)

    def __init__(self, bot):
        super().__init__(bot)
        self.member_cache: dict[tuple[discord.Guild, discord.Member], discord.Message] = {}
        self.history_cache: dict[discord.TextChannel, list[discord.Message]] = defaultdict(list)

    @BaseCog.listener()
    async def on_message(self, message: discord.Message):
        if message.guild is not None:
            self.member_cache[(message.guild, message.author)] = message
            self.history_cache[message.channel].append(message)

    async def get_last_seen_msg(self, member: discord.Member) -> typing.Optional[discord.Message]:
        last = datetime.datetime.utcnow() - SeenUser.MAX_LOOKBACK
        seen_msg: typing.Optional[discord.Message] = None
        for channel in member.guild.text_channels:  # type: discord.TextChannel
            if (history := self.history_cache.get(channel)) is None:
                if not channel.permissions_for(member.guild.me).read_message_history:
                    continue
                self.history_cache[channel] = history = sorted(
                    await channel.history(limit=None, after=last).flatten(),
                    key=operator.attrgetter('id')
                )
            seen_msg = discord.utils.get(reversed(history), author=member) or seen_msg
            last = getattr(seen_msg, 'created_at', last)
        return seen_msg

    @commands.command()
    async def seen(self, ctx: MyContext, *, member: discord.Member):
        """Returns the last message sent by the given member in the current server.
        Initially looks back up to 24 hours."""
        key = (ctx.guild, member)
        try:
            seen_msg = self.member_cache[key]
        except KeyError:
            async with ctx.typing():
                self.member_cache[key] = seen_msg = await self.get_last_seen_msg(member)
        if seen_msg is None:
            ndelt = naturaldelta(SeenUser.MAX_LOOKBACK)
            # 1 day is parsed to "a day" but that's bad grammar here
            ndelt = re.sub(r'^an? ', '', ndelt)
            await ctx.send(f'{member.display_name} has not said anything on this server in the last {ndelt}.')
        elif seen_msg.channel == ctx.channel:
            await seen_msg.reply(f'{member.display_name} was last seen chatting in this channel '
                                 f'{seen_msg.created_at.strftime("on %d %B %Y at %H:%M:%S UTC")}')
        elif seen_msg.channel.is_nsfw() and not ctx.channel.is_nsfw():
            await ctx.send(f'{member.display_name} was last seen chatting in an NSFW channel '
                           f'{seen_msg.created_at.strftime("on %d %B %Y at %H:%M:%S UTC")}')
        else:
            await ctx.send(f'{member.display_name} was last seen chatting in {seen_msg.channel.mention} '
                           f'{seen_msg.created_at.strftime("on %d %B %Y at %H:%M:%S UTC")}\n'
                           f'{seen_msg.jump_url}')

    @BaseCog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent):
        guild: discord.Guild = self.bot.get_guild(payload.guild_id)
        channel: discord.TextChannel = self.bot.get_channel(payload.channel_id)
        if channel in self.history_cache:
            msg: typing.Optional[discord.Message]
            if (msg := discord.utils.get(self.history_cache[channel], id=payload.message_id)) is not None:
                self.history_cache[channel].remove(msg)
                try:
                    del self.member_cache[(guild, guild.get_member(msg.author.id))]
                except KeyError:
                    pass


def setup(bot: PikalaxBOT):
    bot.add_cog(SeenUser(bot))
