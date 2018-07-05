import asyncio
import discord
from utils.default_cog import Cog
from discord.ext import commands


class Core(Cog):
    disabled_commands = set()
    banlist = set()
    game = '!pikakill'
    config_attrs = 'disabled_commands', 'banlist', 'game'

    async def __global_check(self, ctx: commands.Context):
        if ctx.author.bot:
            return False
        if isinstance(ctx.command, commands.Command):
            if ctx.author == self.bot.user:
                return True
            if ctx.command.name in self.disabled_commands:
                return False
        if ctx.author.id in self.banlist:
            return False
        return ctx.channel.permissions_for(ctx.bot.user).send_messages

    @commands.command(aliases=['pikareboot'])
    @commands.is_owner()
    async def pikakill(self, ctx: commands.Context):
        """Shut down the bot (owner only, manual restart required)"""
        await self.bot.close()

    async def on_ready(self):
        activity = discord.Game(self.game)
        await self.bot.change_presence(activity=activity)


def setup(bot):
    bot.add_cog(Core(bot))
