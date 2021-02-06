import discord
from discord.ext import commands
from . import *
from ..types import *
import typing
import datetime


class DpyGuild(BaseCog):
    HELP_CHANNEL_IDS = {381965515721146390, 564950631455129636, 738572311107469354}
    TESTING_CHANNEL_ID = 381963689470984203

    def __init__(self, bot: PikalaxBOT):
        super().__init__(bot)
        self._mappings = {
            discord.Member: commands.CooldownMapping.from_cooldown(1, 5, commands.BucketType.member),
            discord.Role: commands.CooldownMapping.from_cooldown(1, 5, commands.BucketType.role)
        }

    @property
    def testing(self) -> typing.Optional[discord.TextChannel]:
        return self.bot.get_channel(DpyGuild.TESTING_CHANNEL_ID)

    @staticmethod
    def make_embed(key: typing.Union[discord.Role, discord.Member], is_remove: bool):
        embed = discord.Embed(
            colour=discord.Colour.red(),
            title='Tempblock {}'.format('removed' if is_remove else 'added')
        )
        if isinstance(key, discord.Role):
            embed.set_author(name=key.name)
        else:
            embed.set_author(name=f'{key.display_name} ({key})', icon_url=key.avatar_url)
        embed.timestamp = datetime.datetime.utcnow()
        return embed

    async def log_tempblock_add(self, key: typing.Union[discord.Role, discord.Member]):
        await self.testing.send(embed=DpyGuild.make_embed(key, False))

    async def log_tempblock_remove(self, key: typing.Union[discord.Role, discord.Member]):
        await self.testing.send(embed=DpyGuild.make_embed(key, True))

    @BaseCog.listener()
    async def on_guild_channel_update(self, before: GuildChannel, after: GuildChannel):
        if before.id not in DpyGuild.HELP_CHANNEL_IDS:
            return
        if before.overwrites == after.overwrites:
            return
        for key in before.overwrites | after.overwrites:  # type: typing.Union[discord.Role, discord.Member]
            before_ow: typing.Optional[bool] = before.overwrites_for(key).send_messages
            after_ow: typing.Optional[bool] = after.overwrites_for(key).send_messages
            if before_ow is not False and after_ow is False:
                await self.log_tempblock_add(key)
            elif before_ow is False and after_ow is not False:
                await self.log_tempblock_remove(key)


def setup(bot: PikalaxBOT):
    bot.add_cog(DpyGuild(bot))
