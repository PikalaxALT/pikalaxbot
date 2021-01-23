import discord
from ..bot import PikalaxBOT
from ..context import MyContext
import typing
import asyncpg
import asyncstdlib.functools as afunctools


__all__ = ('command_prefix', 'set_guild_prefix')


@afunctools.cache
async def _guild_prefix(bot: PikalaxBOT, guild: typing.Optional[discord.Guild]) -> typing.Union[str, list[str]]:
    if guild is None:
        return ''
    async with bot.sql as sql:  # type: asyncpg.Connection
        prefix = await sql.fetchval(
            'select prefix '
            'from prefixes '
            'where guild = $1',
            guild.id
        )
    return prefix or bot.settings.prefix


def command_prefix(bot: PikalaxBOT, message: discord.Message):
    return _guild_prefix(bot, message.guild)


async def set_guild_prefix(ctx: MyContext, prefix: str):
    async with ctx.bot.sql as sql:  # type: asyncpg.Connection
        async with sql.transaction():
            await sql.execute(
                'insert into prefixes '
                'values ($1, $2) '
                'on conflict (guild) '
                'do update '
                'set prefix = $2',
                ctx.guild.id,
                prefix
            )
    _guild_prefix.cache_clear()
