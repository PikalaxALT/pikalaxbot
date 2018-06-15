import asyncio
import argparse
import discord
from discord.client import log
from discord.ext import commands
from utils import sql
from utils.botclass import PikalaxBOT
from utils.checks import ctx_can_markov, ctx_can_learn_markov
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


def main():
    bot = PikalaxBOT()
    for extn in initial_extensions:
        bot.load_extension(extn)
    help_bak = bot.remove_command('help')
    help_bak.name = 'pikahelp'
    bot.add_command(help_bak)

    async def _on_ready():
        if not bot.initialized:
            for ch in bot.markov_channels:
                channel = bot.get_channel(ch)  # type: discord.TextChannel
                try:
                    async for msg in channel.history(limit=5000):
                        ctx = await bot.get_context(msg)
                        await bot.learn_markov(ctx, force=True)
                    log.info(f'Initialized channel {channel.name}')
                except discord.Forbidden:
                    log.error(f'Failed to get message history from {channel.name} (403 FORBIDDEN)')
                except AttributeError:
                    log.error(f'Failed to load chain {ch:d}')
            bot.initialized = True
        activity = discord.Game(bot.game)
        await bot.change_presence(activity=activity)

    @bot.event
    async def on_ready():
        typing = []
        bot.whitelist = {ch.id: ch for ch in map(bot.get_channel, bot.whitelist) if ch is not None}
        for channel in bot.whitelist.values():
            typing.append(await channel.typing().__aenter__())
        try:
            await _on_ready()
            for channel in bot.whitelist.values():
                await channel.send('_is active and ready for abuse!_')
            bot.rollback = False
        except Exception as e:
            log.error(''.join(traceback.format_exception(type(e), e, e.__traceback__)))
            raise e
        finally:
            [t.task.cancel() for t in typing]

    @bot.check
    async def is_initialized(ctx):
        return bot.initialized

    @bot.check
    async def is_not_bot(ctx):
        return not ctx.author.bot

    @bot.check
    async def is_not_banned(ctx):
        return ctx.author.id not in bot.banlist

    @bot.check
    async def cmd_is_enabled(ctx: commands.Context):
        return ctx.command.name not in bot.disabled_commands

    @bot.listen('on_message')
    async def send_markov(msg: discord.Message):
        ctx = await bot.get_context(msg)
        if await ctx_can_markov(ctx):
            cmd = bot.get_command('markov')
            if cmd is not None:
                await ctx.invoke(cmd)

    @bot.listen('on_message')
    async def coro_learn_markov(msg):
        ctx = await bot.get_context(msg)
        if await ctx_can_learn_markov(ctx):
            await bot.learn_markov(ctx)

    @bot.listen('on_message_edit')
    async def coro_update_markov(old, new):
        ctx = await bot.get_context(old)
        if await ctx_can_learn_markov(ctx):
            await bot.forget_markov(ctx)
        ctx = await bot.get_context(new)
        if await ctx_can_learn_markov(ctx):
            await bot.learn_markov(ctx)

    @bot.listen('on_message_delete')
    async def coro_delete_markov(msg):
        ctx = await bot.get_context(msg)
        if await ctx_can_learn_markov(ctx):
            await bot.forget_markov(ctx)

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
