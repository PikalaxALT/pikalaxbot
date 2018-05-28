import random
import subprocess
from discord.ext import commands
from utils.checks import ctx_is_owner
from utils import sql


class Core:
    def __init__(self, bot):
        self.bot = bot

    @commands.check
    def is_allowed(self, ctx: commands.Context):
        return ctx.channel.id in self.bot.whitelist and not ctx.author.bot

    @commands.check
    def is_not_me(self, ctx: commands.Context):
        return ctx.author != self.bot.user

    @commands.command(pass_context=True)
    @commands.check(ctx_is_owner)
    async def pikakill(self, ctx: commands.Context):
        """Shut down the bot (owner only, manual restart required)"""
        await ctx.send(f'I don\'t feel so good, Mr. {ctx.author.display_name}...')
        await self.bot.close()
        sql.backup_db()

    @commands.command(pass_context=True)
    @commands.check(ctx_is_owner)
    async def pikareboot(self, ctx: commands.Context, *, force: bool = False):
        """Reboot the bot (owner only)"""
        await ctx.send(f'Rebooting to apply updates...')
        await self.bot.close()
        sql.backup_db()
        if force:
            subprocess.check_call(['git', 'reset', '--hard', 'HEAD~'])
        subprocess.check_call(['git', 'pull'])
        subprocess.Popen(['python3.6', 'bot.py'])


def setup(bot):
    bot.add_cog(Core(bot))
