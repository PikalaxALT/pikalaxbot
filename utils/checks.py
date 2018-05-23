import asyncio
import discord
from discord.ext import commands


async def ctx_is_owner(ctx: commands.Context):
    if await ctx.bot.is_owner(ctx.author):
        return True
    if ctx.command.name != 'pikahelp':
        await ctx.send(f'{ctx.author.mention}: Permission denied')
    return False
