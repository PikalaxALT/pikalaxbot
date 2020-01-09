import discord
from discord.ext import commands
from . import BaseCog
import contextlib


@contextlib.contextmanager
def transform_context(ctx, user, content):
    old_content = ctx.message.content
    old_author = ctx.author
    ctx.message.author = user
    ctx.message.content = ctx.prefix + content
    yield ctx.message
    ctx.message.content = old_content
    ctx.message.author = old_author


class Sudo(BaseCog):
    @commands.is_owner()
    @commands.command()
    async def sudo(self, ctx, user: discord.Member, *, content):
        """Run as someone else"""
        with transform_context(ctx, user, content) as message:
            await self.bot.process_commands(message)


def setup(bot):
    bot.add_cog(Sudo(bot))
