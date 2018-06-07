import asyncio
import discord
import logging
import traceback
from discord.ext import commands
from utils.config_io import Settings
from discord.client import compat, log
from utils.checks import CommandNotAllowed, ctx_can_markov, ctx_can_learn_markov


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
            self.banlist = set()
            for key, value in settings.items('user'):
                setattr(self, key, value)

        self.chains = {chan: None for chan in self.markov_channels}
        self.storedMsgsSet = set()
        self.rollback = False
        self.banlist = set(self.banlist)
        super().__init__(command_prefix, case_insensitive=True)

    def commit(self):
        whitelist = dict(self.whitelist)
        self.whitelist = list(self.whitelist.keys())
        self.token = self._token
        self.owner = self.owner_id
        self.prefix = self.command_prefix
        with Settings() as settings:
            for group in settings.categories:
                for key in settings.keys(group):
                    settings.set(group, key, getattr(self, key, None))
        self.whitelist = whitelist
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
            for handler in log.handlers:  # type: logging.Handler
                handler.flush()

    async def learn_markov(self, ctx, force=False):
        if await ctx_can_learn_markov(ctx, force=force):
            self.storedMsgsSet.add(ctx.message.clean_content)
            self.chains[ctx.channel.id].learn_str(ctx.message.clean_content)

    async def forget_markov(self, ctx, force=False):
        if await ctx_can_learn_markov(ctx, force=force):
            self.chains[ctx.channel.id].unlearn_str(ctx.message.clean_content)
