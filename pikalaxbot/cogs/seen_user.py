import datetime
import discord
from collections import defaultdict
from discord.ext import commands
import typing
from . import BaseCog
from humanize import naturaldelta
import re


def get_msg_reference(message):
    return discord.MessageReference(
        None,  # message._state
        message_id=message.id,
        channel_id=message.channel.id,
        guild_id=message.guild.id
    )


def get_jump_url(ref):
    return f'https://discordapp.com/channels/{ref.guild_id}/{ref.channel_id}/{ref.message_id}'


class SeenUser(BaseCog):
    MAX_LOOKBACK = datetime.timedelta(days=1)

    def __init__(self, bot):
        super().__init__(bot)
        self.member_cache = {}
        self.history_cache = defaultdict(list)

    @BaseCog.listener()
    async def on_message(self, message: discord.Message):
        if message.guild is not None:
            ref = get_msg_reference(message)
            self.member_cache[(message.guild.id, message.author.id)] = ref
            self.history_cache[message.channel.id].append((message.author.id, ref))

    async def get_last_seen_msg(self, member: discord.Member) -> typing.Optional[discord.MessageReference]:
        last = datetime.datetime.utcnow() - SeenUser.MAX_LOOKBACK
        seen_msg: typing.Optional[discord.MessageReference] = None
        for channel in member.guild.text_channels:  # type: discord.TextChannel
            if channel.id in self.history_cache:
                history = self.history_cache[channel.id]
            elif channel.permissions_for(member.guild.me).read_message_history:
                history = [(message.author.id, get_msg_reference(message)) async for message in channel.history(limit=None, after=last)]
                if history:
                    history.sort(key=lambda msg: discord.utils.snowflake_time(msg[1].message_id))
                self.history_cache[channel.id] = history
            else:
                continue
            _, seen_msg = discord.utils.find(lambda m: m[0] == member.id, reversed(history)) or seen_msg
            if seen_msg is not None:
                last = discord.utils.snowflake_time(seen_msg.message_id)
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
            ndelt = naturaldelta(SeenUser.MAX_LOOKBACK)
            # 1 day is parsed to "a day" but that's bad grammar here
            ndelt = re.sub(r'^an? ', '', ndelt)
            await ctx.send(f'{member.display_name} has not said anything on this server in the last {ndelt}.')
        else:
            await ctx.send(f'{member.display_name} was last seen chatting in <#{seen_msg.channel_id}> '
                           f'{discord.utils.snowflake_time(seen_msg.message_id).strftime("on %d %B %Y at %H:%M:%S UTC")}\n'
                           f'{get_jump_url(seen_msg)}')


def setup(bot):
    bot.add_cog(SeenUser(bot))
