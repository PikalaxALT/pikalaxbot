import asyncio
import discord
import logging
import traceback
from discord.ext import commands
from utils.config_io import Settings
from discord.client import log
from utils.checks import can_learn_markov
from utils import markov, sql


class PikalaxBOT(commands.Bot):
    whitelist = []
    debug = False
    markov_channels = []
    cooldown = 10
    initialized = False
    command_prefix = '!'
    help_name = 'pikahelp'
    game = f'{command_prefix}{help_name}'
    banlist = set()
    disabled_commands = set()
    voice_chans = {}
    disabled_cogs = []

    def __init__(self, script):
        self.script = script
        with Settings() as settings:
            command_prefix = settings.get('meta', 'prefix', '!')
            super().__init__(command_prefix, case_insensitive=True, helpattrs={'name': self.help_name})
            self._token = settings.get('credentials', 'token')
            self.owner_id = settings.get('credentials', 'owner')
            for key, value in settings.items('user'):
                setattr(self, key, value)
            self.commit()

        self.chain = markov.Chain(store_lowercase=True)
        self.storedMsgsSet = set()
        self.banlist = set(self.banlist)
        self.disabled_commands = set(self.disabled_commands)

    def commit(self):
        whitelist = dict(self.whitelist)
        self.whitelist = list(self.whitelist.keys())
        self.token = self._token
        self.owner = self.owner_id
        self.prefix = self.command_prefix
        self.disabled_commands = list(self.disabled_commands)
        self.banlist = list(self.banlist)
        with Settings() as settings:
            for group in settings.categories:
                for key in settings.keys(group):
                    settings.set(group, key, getattr(self, key, None))
        self.whitelist = whitelist
        self.disabled_commands = set(self.disabled_commands)
        self.banlist = set(self.banlist)
        delattr(self, 'token')
        delattr(self, 'owner')
        delattr(self, 'prefix')

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

    def print(self, message):
        log.debug(message)

    async def close(self, is_int=True):
        if is_int and isinstance(self.whitelist, dict):
            for channel in self.whitelist.values():
                await channel.send('Shutting down... (console kill)')
        await super().close()
        self.commit()
        sql.backup_db()

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

    async def on_command_error(self, context, exception):
        await super().on_command_error(context, exception)
        emoji = self.find_emoji_in_guild(context.guild, 'tppBurrito', 'VeggieBurrito', default='❤')
        if isinstance(exception, commands.NotOwner) and context.command.name != 'pikahelp':
            await context.send(f'{context.author.mention}: Permission denied {emoji}')
        elif isinstance(exception, NotImplemented):
            await context.send(f'{context.author.mention}: The command or one of its dependencies is '
                               f'not fully implemented {emoji}')
        tb = traceback.format_exception(type(exception), exception, exception.__traceback__)
        log.error(tb[0])
        for handler in log.handlers:  # type: logging.Handler
            handler.flush()

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
