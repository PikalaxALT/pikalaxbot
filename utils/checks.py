import asyncio
import discord
from discord.ext import commands


class CommandNotAllowed(commands.CheckFailure):
    pass


async def ctx_is_owner(ctx):
    if await ctx.bot.is_owner(ctx.author):
        return True
    raise CommandNotAllowed


async def ctx_markov_general_checks(ctx):
    return ctx.bot.general_markov_checks(ctx.message)


async def ctx_can_markov(ctx):
    return ctx.bot.can_markov(ctx.message)


async def ctx_can_learn_markov(ctx):
    return ctx.bot.can_learn_markov(ctx.message, force=False)
