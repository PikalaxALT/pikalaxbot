import asyncio
import discord
import subprocess
import traceback
from utils.botclass import PikalaxBOT
from discord.ext import commands
from discord.client import log
from utils.checks import ctx_is_owner, ctx_can_markov, ctx_can_learn_markov


class Core:
    def __init__(self, bot):
        self.bot: PikalaxBOT = bot

    async def __global_check(self, ctx: commands.Context):
        if not self.bot.initialized:
            return False
        if ctx.channel.id not in self.bot.whitelist:
            return False
        if ctx.author.bot:
            return False
        if isinstance(ctx.command, commands.Command):
            if ctx.author == self.bot.user:
                return True
            if ctx.command.name in self.bot.disabled_commands:
                return False
        if ctx.author.id in self.bot.banlist:
            return False
        return True

    @commands.command(pass_context=True)
    @commands.check(ctx_is_owner)
    async def pikakill(self, ctx: commands.Context):
        """Shut down the bot (owner only, manual restart required)"""
        for chan in self.bot.whitelist.values():
            await chan.send(f'I don\'t feel so good, Mr. {ctx.author.display_name}...')
        await self.bot.close(is_int=False)

    @commands.command(pass_context=True)
    @commands.check(ctx_is_owner)
    async def pikareboot(self, ctx: commands.Context, *, force: bool = False):
        """Reboot the bot (owner only)"""
        for chan in self.bot.whitelist.values():
            await chan.send(f'Rebooting to apply updates...')
        await self.bot.close(is_int=False)
        if force:
            subprocess.check_call(['git', 'reset', '--hard', 'HEAD~'])
        subprocess.check_call(['git', 'pull'])
        subprocess.Popen(['python3.6', self.bot.script])

    async def on_ready(self):
        typing = []
        self.bot.whitelist = {ch.id: ch for ch in map(self.bot.get_channel, self.bot.whitelist) if ch is not None}
        for channel in self.bot.whitelist.values():
            typing.append(await channel.typing().__aenter__())
        try:
            await self.bot.on_ready()
            for channel in self.bot.whitelist.values():
                await channel.send('_is active and ready for abuse!_')
            self.bot.rollback = False
        except Exception as e:
            log.error(''.join(traceback.format_exception(type(e), e, e.__traceback__)))
            raise e
        finally:
            [t.task.cancel() for t in typing]

    async def on_message(self, msg: discord.Message):
        ctx = await self.bot.get_context(msg)
        if await ctx_can_learn_markov(ctx):
            await self.bot.learn_markov(ctx)
        if await ctx_can_markov(ctx):
            cmd = self.bot.get_command('markov')
            if cmd is not None:
                await ctx.invoke(cmd)

    async def on_message_edit(self, old, new):
        ctx = await self.bot.get_context(old)
        if await ctx_can_learn_markov(ctx):
            await self.bot.forget_markov(ctx)
        ctx = await self.bot.get_context(new)
        if await ctx_can_learn_markov(ctx):
            await self.bot.learn_markov(ctx)

    async def on_message_delete(self, msg):
        ctx = await self.bot.get_context(msg)
        if await ctx_can_learn_markov(ctx):
            await self.bot.forget_markov(ctx)


def setup(bot):
    bot.add_cog(Core(bot))
