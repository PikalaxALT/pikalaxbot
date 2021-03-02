import discord
from discord.ext import commands
import typing
import operator
from . import *


GuildChannel = typing.Union[
    discord.TextChannel,
    discord.VoiceChannel,
    discord.CategoryChannel,
]


class Channels(BaseCog):
    """Commands related to managing guild channels"""

    EMOJIS = {
        discord.ChannelType.text: '#️⃣',
        discord.ChannelType.voice: '🔊',
        discord.ChannelType.news: '📢',
        discord.ChannelType.store: '🏪',
    }

    def get_channel_repr(self, channel: GuildChannel):
        if channel.type is discord.ChannelType.text:
            if channel == channel.guild.rules_channel:
                emoji = '🗒️'
            elif channel.is_nsfw():
                emoji = '🔞'
            else:
                emoji = '#️⃣'
        else:
            emoji = self.EMOJIS[channel.type]
        return '{} {.name}'.format(emoji, channel)

    @commands.group(invoke_without_command=True)
    async def channels(self, ctx: MyContext):
        """Shows the channel list"""
        embed = discord.Embed(
            title=f'Channels I can read in {ctx.guild}',
            colour=0xF47FFF
        )

        perms = operator.attrgetter('read_messages', 'read_message_history')

        def predicate(chan: discord.abc.GuildChannel):
            return any(perms(chan.permissions_for(ctx.guild.me)))

        for category, channels in ctx.guild.by_category():  \
                # type: typing.Optional[discord.CategoryChannel], list[discord.TextChannel]
            channels = [channel for channel in channels if predicate(channel)]
            if not channels:
                continue
            embed.add_field(
                name=str(category or '\u200b'),
                value='\n'.join(map(self.get_channel_repr, channels)),
                inline=False
            )
        await ctx.send(embed=embed)


def setup(bot: PikalaxBOT):
    bot.add_cog(Channels(bot))
