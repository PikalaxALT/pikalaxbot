import discord
from discord.ext import commands, menus
import typing
from . import *
from .utils.menus import NavMenuPages
from ..constants import *


class HoistersMenu(NavMenuPages):
    async def start(self, ctx: MyContext, *, channel=None, wait=False):
        self.emojis = {stat: discord.utils.get(ctx.bot.emojis, name=f'status_{stat}') for stat in discord.Status}
        await super().start(ctx, channel=channel, wait=wait)


class HoisterPageSource(menus.ListPageSource):
    @discord.utils.cached_property
    def num_entries(self):
        return len(self.entries)

    def format_page(self, menu: HoistersMenu, entry: typing.List[discord.Member]):
        try:
            mbd = discord.Embed(title='Accused of hoisting', colour=discord.Colour.dark_red())
            first_idx = menu.current_page * self.per_page + 1
            max_idx = self.num_entries
            last_idx = min(max_idx, first_idx + self.per_page - 1)
            for i, member in enumerate(entry, first_idx):
                nick = discord.utils.escape_markdown(member.nick) if member.nick else 'No nickname'
                emoji = menu.emojis[member.status]
                mbd.add_field(
                    name=f'[{i}] {member}',
                    value=f'**Nickname:** {nick}\n'
                          f'**User ID:** {member.id}\n'
                          f'**Status:** {emoji} {member.status}'
                )
            if first_idx == last_idx:
                footer_text = f'Member {first_idx} of {max_idx}'
            else:
                footer_text = f'Members {first_idx}-{last_idx} of {max_idx}'
            mbd.set_footer(text=footer_text)
            return mbd
        except Exception as e:
            menu.bot.dispatch('command_error', menu.ctx, e)
            return menu.stop()


class Hoisters(BaseCog):
    """Commands for inspecting users who are elevating their names to the top
    of the user list. Restricted to the discord.py guild where this is regulated."""

    @staticmethod
    def is_hoisting(member: discord.Member):
        return not any(role.hoist for role in member.roles) \
            and not member.bot \
            and member.display_name < '0'

    def cog_check(self, ctx: MyContext):
        return ctx.guild.id == DPY_GUILD_ID

    @commands.max_concurrency(1, commands.BucketType.channel)
    @commands.command(name='hoisters')
    async def get_hoisters(self, ctx: MyContext):
        """Get a list of all people in the server whose names are hoisted"""

        hoisters = sorted(
            filter(Hoisters.is_hoisting, ctx.guild.members),
            key=lambda m: (m.nick is None, m.status is discord.Status.offline, m.display_name)
        )
        if not hoisters:
            return await ctx.send('No hoisters found')
        menu = HoistersMenu(HoisterPageSource(hoisters, per_page=9), delete_message_after=True)
        await menu.start(ctx, wait=True)

    @commands.command(name='is-hoisting', aliases=['hoisting'])
    async def is_hoisting_cmd(self, ctx: MyContext, *, member: discord.Member):
        """Returns whether the member in question is hoisting."""

        embed = discord.Embed(
            title='Hoisting report',
            description=f'```\n'
                        f'Display Name: {member.display_name}\n'
                        f'User ID:      {member.id}\n'
                        f'Is bot:       {member.bot}\n'
                        f'Is hoisting:  {Hoisters.is_hoisting(member)}\n'
                        f'```',
            colour=0xf47fff
        ).set_author(name=str(member), icon_url=str(member.avatar_url))

        await ctx.send(embed=embed)


def setup(bot: PikalaxBOT):
    bot.add_cog(Hoisters(bot))
