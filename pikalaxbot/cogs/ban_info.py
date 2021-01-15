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
from discord.ext import commands, menus
from . import *
import aioitertools


class BanInfoPageSource(menus.PageSource):
    def __init__(self, guild: discord.Guild):
        super().__init__()
        self.iterator: discord.guild.AuditLogIterator = guild.audit_logs(limit=None, action=discord.AuditLogAction.ban)
        self._cache: list[discord.AuditLogEntry] = []
        self._ncache = 0
        self._more = True
        self._n_last_fetched = 0

    async def fetchmany(self, n=1):
        if not self._more or n < 1:
            return
        self._cache += [entry async for self._n_last_fetched, entry in aioitertools.zip(range(n), self.iterator)]
        if self._n_last_fetched < n:
            self._more = False
        self._ncache += self._n_last_fetched

    async def fetchone(self):
        try:
            entry: discord.AuditLogEntry = await self.iterator.next()
        except discord.NoMoreItems:
            self._more = False
        else:
            self._cache.append(entry)
            self._ncache += 1

    async def prepare(self):
        await self.fetchmany(100)

    def is_paginating(self):
        return self._ncache >= 2

    async def get_page(self, page_number):
        await self.fetchmany(page_number - self._ncache)
        return self._cache[min(page_number, self._ncache - 1)]

    def get_max_pages(self):
        return self._more and None or self._ncache

    async def format_page(self, menu: menus.MenuPages, page: discord.AuditLogEntry):
        guild: discord.Guild = menu.ctx.guild
        embed = discord.Embed(
            title=f'Ban Log for {guild}',
            description=f'**Target:** {page.target} ({page.target.id})\n'
                        f'**Reason:** {page.reason or "No reason given"}',
            colour=discord.Colour.red()
        ).set_author(
            name=page.user.name,
            icon_url=str(page.user.avatar_url)
        ).set_thumbnail(
            url=str(page.target.avatar_url)
        ).set_footer(
            text=f'Entry {menu.current_page + 1} of {self.get_max_pages() or "???"}'
        )
        embed.timestamp = page.created_at
        return embed


class BanInfo(BaseCog):
    """Commands related to retrieving server bans"""
    @commands.command('ban-info')
    async def ban_info(self, ctx: MyContext):
        """Get the entire ban log"""
        menu = menus.MenuPages(BanInfoPageSource(ctx.guild), delete_message_after=True)
        try:
            await menu.start(ctx)
        except IndexError:
            await ctx.send('No bans to speak of')


def setup(bot: PikalaxBOT):
    bot.add_cog(BanInfo(bot))
