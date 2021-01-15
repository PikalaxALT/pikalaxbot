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

from discord.ext import commands
from . import *
from .utils.game import find_emoji
import asyncpg


class Bag(BaseCog):
    """Commands related to Lillie's bag. Get in, Nebby."""

    default_bag = (
        ('happily jumped into the bag!',),
        ('reluctantly clambored into the bag.',),
        ('turned away!',),
        ('let out a cry in protest!',)
    )

    async def init_db(self, sql):
        await sql.execute("create table if not exists meme (bag text unique)")
        await sql.executemany("insert into meme values ($1) on conflict (bag) do nothing", self.default_bag)

    @commands.group(invoke_without_command=True)
    async def bag(self, ctx: MyContext):
        """Get in the bag, Nebby."""
        async with self.bot.sql as sql:  # type: asyncpg.Connection
            if message := await sql.fetchval('select bag from meme order by random() limit 1'):  # type: str
                await ctx.send(f'*{message}*')
            else:
                emoji = find_emoji(ctx.bot, 'BibleThump', case_sensitive=False)
                await ctx.send(f'*cannot find the bag {emoji}*')

    @bag.command()
    async def add(self, ctx: MyContext, *, fmtstr: str):
        """Add a message to the bag."""
        try:
            async with self.bot.sql as sql:  # type: asyncpg.Connection
                await sql.execute('insert into meme values ($1)', fmtstr)
        except asyncpg.PostgresError:
            await ctx.send('That message is already in the bag')
        else:
            await ctx.send('Message was successfully placed in the bag')

    @bag.command(name='remove')
    @commands.is_owner()
    async def remove_bag(self, ctx: MyContext, *, msg: str):
        """Remove a phrase from the bag"""
        if msg in self.default_bag:
            return await ctx.send('Cannot remove default message from bag')
        try:
            async with self.bot.sql as sql:  # type: asyncpg.Connection
                await sql.execute('delete from meme where bag = $1', msg)
        except asyncpg.PostgresError:
            await ctx.send('Cannot remove message from the bag')
        else:
            await ctx.send('Removed message from bag')

    @bag.command(name='reset')
    @commands.is_owner()
    async def reset_bag(self, ctx: MyContext):
        """Reset the bag"""
        async with self.bot.sql as sql:  # type: asyncpg.Connection
            await sql.execute('drop table meme')
            await self.init_db(sql)
        await ctx.send('Reset the bag')


def setup(bot: PikalaxBOT):
    bot.add_cog(Bag(bot))
