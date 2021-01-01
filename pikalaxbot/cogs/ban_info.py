import discord
from discord.ext import commands, menus
from . import BaseCog
import typing
if typing.TYPE_CHECKING:
    from .. import PikalaxBOT


class BanInfoPageSource(menus.PageSource):
    def __init__(self, guild: discord.Guild):
        super().__init__()
        self.iterator: typing.AsyncIterator[discord.AuditLogEntry] = guild.audit_logs(limit=None, action=discord.AuditLogAction.ban)
        self._cache: typing.List[discord.AuditLogEntry] = []
        self._ncache = 0
        self._more = True

    async def fetchmany(self, n=1):
        if not self._more or n < 1:
            return
        n += self._ncache
        async for entry in self.iterator:
            self._cache.append(entry)
            self._ncache += 1
            if self._ncache == n:
                break
        else:
            self._more = False

    async def prepare(self):
        await self.fetchmany(2)

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
        )
        embed.timestamp = page.created_at
        return embed


class BanInfo(BaseCog):
    @commands.command('ban-info')
    async def ban_info(self, ctx: commands.Context):
        """Get the entire ban log"""
        menu = menus.MenuPages(BanInfoPageSource(ctx.guild))
        try:
            await menu.start(ctx)
        except IndexError:
            await ctx.send('No bans to speak of')


def setup(bot: 'PikalaxBOT'):
    bot.add_cog(BanInfo(bot))
