import datetime
import discord
from collections import defaultdict
from discord.ext import commands
import typing
from . import BaseCog
from humanize import naturaldelta
import re
if typing.TYPE_CHECKING:
    from .. import PikalaxBOT


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
                self.history_cache[channel] = history = sorted(await channel.history(limit=None, after=last).flatten(), key=lambda msg: msg.created_at)
            last = getattr((seen_msg := discord.utils.get(reversed(history), author=member) or seen_msg), 'created_at', last)
        return seen_msg

    @commands.command()
    async def seen(self, ctx: commands.Context, *, member: discord.Member):
        """Returns the last message sent by the given member in the current server.
        Initially looks back up to 24 hours."""
        key = (ctx.guild, member)
        if (seen_msg := self.member_cache.get(key)) is None:
            self.member_cache[key] = seen_msg = await self.get_last_seen_msg(member)
        if seen_msg is None:
            ndelt = naturaldelta(SeenUser.MAX_LOOKBACK)
            # 1 day is parsed to "a day" but that's bad grammar here
            ndelt = re.sub(r'^an? ', '', ndelt)
            await ctx.send(f'{member.display_name} has not said anything on this server in the last {ndelt}.')
        else:
            await ctx.send(f'{member.display_name} was last seen chatting in <#{seen_msg.channel_id}> '
                           f'{seen_msg.created_at.strftime("on %d %B %Y at %H:%M:%S UTC")}\n'
                           f'{seen_msg.jump_url}')


def setup(bot: 'PikalaxBOT'):
    bot.add_cog(SeenUser(bot))
