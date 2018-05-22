import asyncio
import discord
from discord.ext import commands
from discord import compat
from discord.client import log
from utils import markov, sql
from utils.config_io import Settings
from utils.checks import ctx_is_owner
import random
import logging
import sys
import traceback
import subprocess

initial_extensions = (
    'cogs.meme',
    'cogs.hangman',
    'cogs.anagram',
    'cogs.trashcans',
    'cogs.leaderboard',
    'cogs.voltorb_flip',
    'cogs.modtools',
)


def log_exc(exc):
    log.error(traceback.format_exception(type(exc), exc, exc.__traceback__))


class PikalaxBOT(commands.Bot):
    def __init__(self):
        with Settings() as settings:
            command_prefix = settings.get('meta', 'prefix', '!')
            self._token = settings.get('credentials', 'token')
            self.owner_id = settings.get('credentials', 'owner')
            self.whitelist = []
            self.debug = False
            self.markov_channels = []
            self.cooldown = 10
            self.initialized = False
            self.game = f'{command_prefix}pikahelp'
            for key, value in settings.items('user'):
                setattr(self, key, value)

        self.chains = {chan: None for chan in self.markov_channels}

        self.storedMsgsSet = set()

        super().__init__(command_prefix, case_insensitive=True)

    def run(self):
        super().run(self._token)

    def print(self, message):
        if self.debug:
            print(message)

    def _do_cleanup(self):
        loop = self.loop

        if loop.is_closed():
            return

        for channel in self.whitelist.values():
            compat.create_task(channel.send('Shutting down... (console kill)'), loop=loop)

        if not loop.is_running():
            loop.run_forever()

        super()._do_cleanup()

    def gen_msg(self, ch, len_max=64, n_attempts=5):
        longest = ''
        lng_cnt = 0
        chain = self.chains.get(ch)
        if chain is not None:
            for i in range(n_attempts):
                cur = chain.generate(len_max)
                if len(cur) > lng_cnt:
                    msg = ' '.join(cur)
                    if i == 0 or msg not in self.storedMsgsSet:
                        lng_cnt = len(cur)
                        longest = msg
                        if lng_cnt == len_max:
                            break
        return longest

    async def on_command_error(self, context, exception):
        if not self.debug and isinstance(exception, commands.CommandError):
            await super().on_command_error(context, exception)
        else:
            tb = traceback.format_exception(type(exception), exception, exception.__traceback__)
            log.error(tb[0])

    def markov_general_checks(self, msg):
        if not self.initialized:
            return False
        if msg.channel.id not in self.whitelist:
            return False
        if msg.author.bot:
            return False
        if len(self.chains) == 0:
            return False
        return True

    def can_markov(self, msg):
        if not self.markov_general_checks(msg):
            return False
        if self.user.mentioned_in(msg):
            return True
        if self.user.name.lower() in msg.clean_content.lower():
            return True
        if self.user.display_name.lower() in msg.clean_content.lower():
            return True
        return False

    def can_learn_markov(self, msg, force=False):
        if not (force or self.markov_general_checks(msg)):
            return False
        if msg.author.bot:
            return False
        return msg.channel.id in bot.chains and not msg.clean_content.startswith(bot.command_prefix)

    def learn_markov(self, msg, force=False):
        if self.can_learn_markov(msg, force=force):
            self.storedMsgsSet.add(msg.clean_content)
            self.chains[msg.channel.id].learn_str(msg.clean_content)
    
    def forget_markov(self, msg, force=False):
        if self.can_learn_markov(msg, force=force):
            self.chains[msg.channel.id].unlearn_str(msg.clean_content)


if __name__ == '__main__':
    sql.db_init()
    handler = logging.StreamHandler(stream=sys.stderr)
    fmt = logging.Formatter()
    handler.setFormatter(fmt)
    log.addHandler(handler)
    bot = PikalaxBOT()
    log.setLevel(logging.INFO)
    for extn in initial_extensions:
        bot.load_extension(extn)
    help_bak = bot.remove_command('help')
    help_bak.name = 'pikahelp'
    bot.add_command(help_bak)


    @bot.check
    def is_allowed(ctx: commands.Context):
        return ctx.channel.id in ctx.bot.whitelist and not ctx.author.bot


    @bot.check
    def is_not_me(ctx: commands.Context):
        return ctx.author != ctx.bot.user


    @bot.event
    async def on_ready():
        bot.whitelist = {ch.id: ch for ch in map(bot.get_channel, bot.whitelist) if ch is not None}
        for channel in bot.whitelist.values():
            await channel.trigger_typing()
        for ch in list(bot.chains.keys()):
            if bot.chains[ch] is not None:
                del bot.chains[ch]
            bot.chains[ch] = markov.Chain(store_lowercase=True)
            channel = bot.get_channel(ch)  # type: discord.TextChannel
            try:
                async for msg in channel.history(limit=5000):
                    bot.learn_markov(msg, force=True)
                log.info(f'Initialized channel {channel.name}')
            except discord.Forbidden:
                bot.chains.pop(ch)
                log.error(f'Failed to get message history from {channel.name} (403 FORBIDDEN)')
            except AttributeError:
                bot.chains.pop(ch)
                log.error(f'Failed to load chain {ch:d}')
        bot.initialized = True
        activity = discord.Game(bot.game)
        await bot.change_presence(activity=activity)
        for channel in bot.whitelist.values():
            await channel.send('_is active and ready for abuse!_')


    @bot.check
    def is_initialized(ctx):
        return ctx.bot.initialized


    @bot.listen('on_message')
    async def send_markov(msg: discord.Message):
        if bot.can_markov(msg):
            ch = random.choice(list(bot.chains.keys()))
            chain = bot.gen_msg(ch, len_max=250, n_attempts=10)
            if chain:
                await msg.channel.send(f'{msg.author.mention}: {chain}')
            else:
                await msg.channel.send(f'{msg.author.mention}: An error has occurred.')


    @bot.listen('on_message')
    async def coro_learn_markov(msg):
        bot.learn_markov(msg)


    @bot.listen('on_message_edit')
    async def coro_update_markov(old, new):
        bot.forget_markov(old)
        bot.learn_markov(new)


    @bot.listen('on_message_delete')
    async def coro_delete_markov(msg):
        bot.forget_markov(msg)


    @bot.command(pass_context=True)
    @commands.check(ctx_is_owner)
    async def pikakill(ctx: commands.Context):
        await ctx.send('Shutting down...')
        await bot.close()


    @bot.command(pass_context=True)
    @commands.check(ctx_is_owner)
    async def pikareboot(ctx: commands.Context, *, force=False):
        await ctx.send('Shutting down...')
        await bot.close()
        if force:
            subprocess.check_call(['git', 'reset', '--hard', 'HEAD~'])
        subprocess.check_call(['git', 'pull'])
        subprocess.Popen(['python3.6', __file__])


    log.info('Starting bot')
    bot.run()

