import asyncio
import argparse
import discord
from discord.ext import commands
from discord import compat
from discord.client import log
from utils import markov, sql
from utils.config_io import Settings
from utils.checks import CommandNotAllowed
import logging
import sys
import traceback

initial_extensions = (
    'cogs.core',
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
        self.rollback = False
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

        if isinstance(self.whitelist, dict):
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
        if isinstance(exception, CommandNotAllowed) and context.command.name != 'pikahelp':
            emoji = discord.utils.find(lambda e: e.name == 'tppBurrito', context.guild.emojis)
            await context.send(f'{context.author.mention}: Permission denied {emoji}')
        elif not self.debug and isinstance(exception, commands.CommandError):
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
        words = msg.clean_content.lower().split()
        if self.user.name.lower() in words:
            return True
        if self.user.display_name.lower() in words:
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


bot = PikalaxBOT()
for extn in initial_extensions:
    bot.load_extension(extn)
help_bak = bot.remove_command('help')
help_bak.name = 'pikahelp'
bot.add_command(help_bak)


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
        if bot.rollback:
            await channel.send('Update failed, bot was rolled back to a previous version.')
    bot.rollback = False


@commands.check
def is_initialized(ctx):
    return ctx.bot.initialized


@bot.listen('on_message')
async def send_markov(msg: discord.Message):
    ctx = await bot.get_context(msg)
    cmd = bot.get_command('markov')
    if cmd is not None:
        await ctx.invoke(cmd)


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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--rollback', action='store_true')
    args = parser.parse_args()
    bot.rollback = args.rollback

    sql.db_init()
    handler = logging.StreamHandler(stream=sys.stderr)
    fmt = logging.Formatter()
    handler.setFormatter(fmt)
    log.addHandler(handler)
    log.setLevel(logging.INFO)

    log.info('Starting bot')
    bot.run()


if __name__ == '__main__':
    main()
