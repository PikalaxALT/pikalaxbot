import discord
from discord.ext import commands
from . import *
import contextlib


@contextlib.contextmanager
def transform_context(ctx: MyContext, user: discord.Member, content: str):
    old_content = ctx.message.content
    old_author = ctx.author
    ctx.message.author = user
    prefix, *_ = await ctx.bot.get_prefix(ctx.message)
    ctx.message.content = prefix + content
    yield ctx.message
    ctx.message.content = old_content
    ctx.message.author = old_author


class Sudo(BaseCog):
    """Commands for executing a command as someone else."""

    @commands.is_owner()
    @commands.command()
    async def su(self, ctx: MyContext, user: discord.Member, *, content: str):
        """Run as someone else"""
        try:
            with transform_context(ctx, user, content) as message:  # type: discord.Message
                await self.bot.process_commands(message)
        except commands.CommandError:
            pass


def setup(bot):
    bot.add_cog(Sudo(bot))
