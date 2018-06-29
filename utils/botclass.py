import asyncio
import discord
import logging
import os
import glob
import traceback
from discord.ext import commands
from utils.config_io import Settings
from discord.client import log
from utils.checks import can_learn_markov, VoiceCommandError
from utils import markov, sql
import typing


class PikalaxBOT(commands.Bot):
    __attr_mapping__ = {
        'token': '_token',
        'prefix': 'command_prefix',
        'owner': 'owner_id'
    }
    __type_mapping__ = {
        'whitelist': dict,
        'banlist': set,
        'disabled_commands': set
    }
    __slots__ = (
        'whitelist', 'debug', 'markov_channels', 'cooldown', 'command_prefix', 'help_name',
        'game', 'banlist', 'disabled_commands', 'voice_chans', 'disabled_cogs', 'espeak_kw'
    )
    initialized = False
    storedMsgsSet = set()

    def __init__(self, args):
        log.setLevel(logging.DEBUG if args.debug else logging.INFO)
        handler = logging.FileHandler(args.logfile, mode='w')
        fmt = logging.Formatter('%(asctime)s (PID:%(process)s) - %(levelname)s - %(message)s')
        handler.setFormatter(fmt)
        log.addHandler(handler)

        with Settings() as settings:
            command_prefix = settings.get('meta', 'prefix', '!')
            self._token = settings.get('credentials', 'token')
            self.owner_id = settings.get('credentials', 'owner')
            for key, value in settings.items('user'):
                tp: typing.Type = self.__type_mapping__.get(key)
                if tp is not None:
                    if tp is dict and isinstance(value, list):
                        value = {k_: None for k_ in value}
                    else:
                        value = tp(value)
                key = self.__attr_mapping__.get(key, key)
                setattr(self, key, value)
            super().__init__(command_prefix, case_insensitive=True, help_attrs={'name': self.help_name})
            self.commit()

        self.chain = markov.Chain(store_lowercase=True)

        dname = os.path.dirname(__file__) or '.'
        for cogfile in glob.glob(f'{dname}/../cogs/*.py'):
            if os.path.isfile(cogfile) and '__init__' not in cogfile:
                extn = f'cogs.{os.path.splitext(os.path.basename(cogfile))[0]}'
                if extn.split('.')[1] not in self.disabled_cogs:
                    try:
                        self.load_extension(extn)
                    except discord.ClientException:
                        log.warning(f'Failed to load cog "{extn}"')
                    else:
                        log.info(f'Loaded cog "{extn}"')
                else:
                    log.info(f'Skipping disabled cog "{extn}"')

        sql.db_init()

    def commit(self):
        with Settings() as settings:
            for group in settings.categories:
                for key in settings.keys(group):
                    attr = self.__attr_mapping__.get(key, key)
                    val = getattr(self, attr, None)
                    if key == 'whitelist' and isinstance(val, dict):
                        val = list(val.keys())
                    elif isinstance(val, set) and val is not None:
                        val = list(val)
                    settings.set(group, key, val)

    def ban(self, person):
        self.banlist.add(person.id)
        self.commit()

    def unban(self, person):
        self.banlist.remove(person.id)
        self.commit()

    def get_nick(self, guild: discord.Guild):
        member = guild.get_member(self.user.id)
        return member.nick

    def run(self):
        super().run(self._token)

    async def close(self, is_int=True):
        if is_int and isinstance(self.whitelist, dict):
            for channel in self.whitelist.values():
                await channel.send('Shutting down... (console kill)')
        await super().close()
        self.commit()
        await sql.backup_db()

    def gen_msg(self, len_max=64, n_attempts=5):
        longest = ''
        lng_cnt = 0
        chain = self.chain
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

    @staticmethod
    def find_emoji_in_guild(guild, *names, default=None):
        return discord.utils.find(lambda e: e.name in names, guild.emojis) or default

    async def on_command_error(self, ctx, exc):
        # await super().on_command_error(ctx, exc)
        if isinstance(exc, commands.CommandNotFound):
            return

        tb = traceback.format_exception(type(exc), exc, exc.__traceback__)
        emoji = self.find_emoji_in_guild(ctx.guild, 'tppBurrito', 'VeggieBurrito', default='❤')
        if isinstance(exc, VoiceCommandError):
            embed = discord.Embed(color=0xff0000)
            embed.add_field(name='Traceback', value=f'```{tb}```')
            await ctx.send(f'An error has occurred {emoji}', embed=embed)
        elif isinstance(exc, commands.NotOwner) and ctx.command.name != 'pikahelp':
            await ctx.send(f'{ctx.author.mention}: Permission denied {emoji}')
        elif isinstance(exc, commands.MissingPermissions):
            await ctx.send(f'{ctx.author.mention}: I am missing permissions: '
                           f'{", ".join(exc.missing_perms)}')
        elif exc is NotImplemented:
            await ctx.send(f'{ctx.author.mention}: The command or one of its dependencies is '
                           f'not fully implemented {emoji}')

        # Inherit checks from super
        if self.extra_events.get('on_command_error', None):
            return

        if hasattr(ctx.command, 'on_error'):
            return

        cog = ctx.cog
        if cog:
            attr = '_{0.__class__.__name__}__error'.format(cog)
            if hasattr(cog, attr):
                return

        log.error(f'Ignoring exception in command {ctx.command}:')
        log.error(tb)
        # for handler in log.handlers:  # type: logging.Handler
        #     handler.flush()

    def learn_markov(self, ctx):
        self.storedMsgsSet.add(ctx.message.clean_content)
        self.chain.learn_str(ctx.message.clean_content)

    def forget_markov(self, ctx):
        self.chain.unlearn_str(ctx.message.clean_content)
    
    async def on_ready(self):
        if not self.initialized:
            for ch in self.markov_channels:
                channel = self.get_channel(ch)  # type: discord.TextChannel
                try:
                    async for msg in channel.history(limit=5000):
                        ctx = await self.get_context(msg)
                        if can_learn_markov(ctx, force=True):
                            self.learn_markov(ctx)
                    log.info(f'Initialized channel {channel.name}')
                except discord.Forbidden:
                    log.error(f'Failed to get message history from {channel.name} (403 FORBIDDEN)')
                except AttributeError:
                    log.error(f'Failed to load chain {ch:d}')
            self.initialized = True
        activity = discord.Game(self.game)
        await self.change_presence(activity=activity)

    def enable_command(self, cmd):
        res = cmd in self.disabled_commands
        self.disabled_commands.discard(cmd)
        self.commit()
        return res

    def disable_command(self, cmd):
        res = cmd not in self.disabled_commands
        self.disabled_commands.add(cmd)
        self.commit()
        return res
