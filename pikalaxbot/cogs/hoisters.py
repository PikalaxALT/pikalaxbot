import discord
from discord.ext import commands, menus
import typing
from . import BaseCog

DPY_GUILD_ID = 336642139381301249


class HoistersMenu(menus.MenuPages):
    async def start(self, ctx, *, channel=None, wait=False):
        self.emojis = {stat: discord.utils.get(ctx.bot.emojis, name=f'status_{stat}') for stat in discord.Status}
        await super().start(ctx, channel=channel, wait=wait)


class HoisterPageSource(menus.ListPageSource):
    @discord.utils.cached_property
    def num_entries(self):
        return len(self.entries)

    async def format_page(self, menu: HoistersMenu, entry: typing.List[discord.Member]):
        try:
            mbd = discord.Embed(title='Accused of hoisting', colour=discord.Colour.dark_red())
            first_idx = menu.current_page * self.per_page + 1
            max_idx = self.num_entries
            last_idx = min(max_idx, first_idx + self.per_page - 1)
            for i, member in enumerate(entry,first_idx):
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
            await menu.stop()


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
            and member.display_name < '!'
        ]
        hoisters.sort(key=lambda m: (m.nick is None, m.status is discord.Status.offline, m.display_name))
        menu = HoistersMenu(HoisterPageSource(hoisters, per_page=9), delete_message_after=True)
        await menu.start(ctx, wait=True)


def setup(bot):
    bot.add_cog(Hoisters(bot))
