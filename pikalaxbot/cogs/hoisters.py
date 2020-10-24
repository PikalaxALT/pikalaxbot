import discord
from discord.ext import commands, menus
import typing
from . import BaseCog

DPY_GUILD_ID = 336642139381301249


class HoisterPageSource(menus.ListPageSource):
    colormap = {
        discord.Status.online: 0x43B581,
        discord.Status.offline: 0x747F8D,
        discord.Status.dnd: 0xF04747,
        discord.Status.idle: 0xFAA61A
    }

    async def format_page(self, menu: menus.MenuPages, entry: typing.List[discord.Member]):
        mbd = discord.Embed(title='Accused of hoisting', colour=discord.Colour.dark_red())
        for i, member in enumerate(entry, menu.current_page * self.per_page + 1):
            mbd.add_field(name=f'[{i}] Username#dscm', value=member.mention)
            mbd.add_field(name=f'[{i}] Display name', value=member.display_name)
            mbd.add_field(name=f'[{i}] Online status', value=str(member.status))
        mbd.set_footer(text=f'Page {menu.current_page + 1}/{self.get_max_pages()}')
        return mbd


class Hoisters(BaseCog):
    def cog_check(self, ctx):
        return ctx.guild.id == DPY_GUILD_ID

    @commands.max_concurrency(1, commands.BucketType.channel)
    @commands.command(name='hoisters')
    async def get_hoisters(self, ctx):
        """Get a list of all people in the server whose names are hoisted"""

        hoisters = [
            member for member in ctx.guild.members
            if not any(role.hoist for role in member.roles)
            and not member.bot  # bots are exempt
            and member.display_name < '0'
        ]
        hoisters.sort(key=lambda m: (m.status is discord.Status.offline, m.nick is None, m.display_name))
        menu = menus.MenuPages(HoisterPageSource(hoisters, per_page=8), delete_message_after=True)
        await menu.start(ctx, wait=True)


def setup(bot):
    bot.add_cog(Hoisters(bot))
