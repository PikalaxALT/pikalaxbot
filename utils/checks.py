import asyncio
import discord
from discord.ext import commands


class CommandNotAllowed(commands.CheckFailure):
    pass


async def ctx_is_owner(ctx):
    if await ctx.bot.is_owner(ctx.author):
        return True
    raise CommandNotAllowed
