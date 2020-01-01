import datetime
import discord
from collections import defaultdict, namedtuple
from discord.ext import commands
import typing
from . import BaseCog


MessageProxy = namedtuple('MessageProxy', 'message_id author_id channel_id created_at')


def proxy(message):
    return MessageProxy(message.id, message.author.id, message.channel.id, message.created_at)


def get_jump_url(ctx, proxy):
    return f'https://discordapp.com/channels/{ctx.guild.id}/{proxy.channel_id}/{proxy.message_id}'


class SeenUser(BaseCog):
    MAX_LOOKBACK = datetime.timedelta(days=1)

    def __init__(self, bot):
        super().__init__(bot)
        self.member_cache = {}
        self.history_cache = defaultdict(list)

    @BaseCog.listener()
    async def on_message(self, message: discord.Message):
        if message.guild is not None:
            proxy_ = proxy(message)
            self.member_cache[(message.guild.id, message.author.id)] = proxy_
            self.history_cache[message.channel.id].append(proxy_)

    async def get_last_seen_msg(self, member: discord.Member) -> typing.Optional[MessageProxy]:
        last = datetime.datetime.utcnow() - SeenUser.MAX_LOOKBACK
        seen_msg: typing.Optional[MessageProxy] = None
        for channel in member.guild.text_channels:  # type: discord.TextChannel
            if channel.id in self.history_cache:
                history = self.history_cache[channel.id]
            elif channel.permissions_for(member.guild.me).read_message_history:
                history = [proxy(message) async for message in channel.history(limit=None, after=last)]
                if history:
                    history.sort(key=lambda msg: msg.created_at)
                self.history_cache[channel.id] = history
            else:
                continue
            seen_msg = discord.utils.get(reversed(history), author_id=member.id) or seen_msg
            if seen_msg is not None:
                last = seen_msg.created_at
        return seen_msg

    @commands.command()
    async def seen(self, ctx: commands.Context, *, member: discord.Member):
        """Returns the last message sent by the given member in the current server.
        Initially looks back up to 24 hours."""
        key = (ctx.guild.id, member.id)
        if key in self.member_cache:
            seen_msg = self.member_cache[key]
        else:
            seen_msg = await self.get_last_seen_msg(member)
            self.member_cache[key] = seen_msg
        if seen_msg is None:
            await ctx.send(f'{member.display_name} has not said anything on this server recently.')
        else:
            await ctx.send(f'{member.display_name} was last seen chatting in <#{seen_msg.channel_id}> '
                           f'{seen_msg.created_at.strftime("on %d %B %Y at %H:%M:%S UTC")}\n{get_jump_url(seen_msg)}')


def setup(bot):
    bot.add_cog(SeenUser(bot))
