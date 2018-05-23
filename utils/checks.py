import asyncio
import discord
from discord.ext import commands


async def ctx_is_owner(ctx):
    return await ctx.bot.is_owner(ctx.author)
