import asyncio
import discord
from discord.ext import commands
import logging
import os
import glob
import traceback
from utils.config_io import Settings
from utils import sql
from utils.converters import KwargConverterError, EspeakKwargsConverterError


class VoiceCommandError(commands.CommandError):
    """This is raised when an error occurs in a voice command."""


class PikalaxBOT(commands.Bot):
    __attr_mapping__ = {
        'token': '_token',
        'prefix': 'command_prefix',
        'owner': 'owner_id'
    }
    __type_mapping__ = {
        'banlist': set,
        'disabled_commands': set,
        'markov_channel': set
    }

    def __init__(self, args, *, loop=None):
        # Set up logger
        self.logger = logging.getLogger('discord')
        self.logger.setLevel(logging.DEBUG if args.debug else logging.INFO)
        handler = logging.FileHandler(args.logfile, mode='w')
        fmt = logging.Formatter('%(asctime)s (PID:%(process)s) - %(levelname)s - %(message)s')
        handler.setFormatter(fmt)
        self.logger.addHandler(handler)

        # Load settings
        loop = asyncio.get_event_loop() if loop is None else loop
        self.settings = Settings(fname=args.settings)
        with self.settings:
            help_name = self.settings.user.help_name
            command_prefix = self.settings.meta.prefix
            disabled_cogs = self.settings.user.disabled_cogs
        super().__init__(command_prefix, case_insensitive=True, help_attrs={'name': help_name}, loop=loop)

        # Load cogs
        dname = os.path.dirname(__file__) or '.'
        for cogfile in glob.glob(f'{dname}/../cogs/*.py'):
            if os.path.isfile(cogfile) and '__init__' not in cogfile:
                extn = f'cogs.{os.path.splitext(os.path.basename(cogfile))[0]}'
                if extn.split('.')[1] not in disabled_cogs:
                    try:
                        self.load_extension(extn)
                    except discord.ClientException:
                        self.logger.warning(f'Failed to load cog "{extn}"')
                    else:
                        self.logger.info(f'Loaded cog "{extn}"')
                else:
                    self.logger.info(f'Skipping disabled cog "{extn}"')

        # Set up sql database
        sql.db_init()

    @property
    def markov_channels(self):
        cog = self.get_cog('Markov')
        if cog is not None:
            return cog.markov_channels

    @markov_channels.setter
    def markov_channels(self, value):
        cog = self.get_cog('Markov')
        if cog is not None:
            cog.markov_channels = set(value)

    @property
    def espeak_kw(self):
        cog = self.get_cog('YouTube')
        if cog is not None:
            return cog.espeak_kw

    @espeak_kw.setter
    def espeak_kw(self, value):
        cog = self.get_cog('YouTube')
        if cog is not None:
            cog.espeak_kw = value

    @property
    def voice_chans(self):
        cog = self.get_cog('YouTube')
        if cog is not None:
            return cog.voice_chans

    @voice_chans.setter
    def voice_chans(self, value):
        cog = self.get_cog('YouTube')
        if cog is not None:
            cog.voice_chans = value

    def run(self):
        self.logger.info('Starting bot')
        with self.settings:
            token = self.settings.credentials.token
        super().run(token)

    async def login(self, token, *, bot=True):
        for cog in self.cogs.values():
            await cog.fetch()
        await super().login(token, bot=bot)

    async def close(self):
        for cog in self.cogs.values():
            await cog.commit()
        await super().close()
        await sql.backup_db()

    @staticmethod
    def find_emoji_in_guild(guild, *names, default=None):
        return discord.utils.find(lambda e: e.name in names, guild.emojis) or default

    async def on_command_error(self, ctx: commands.Context, exc):
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
        elif isinstance(exc, KwargConverterError):
            msg = f'{ctx.author}: Syntax for {ctx.invoked_with} is "key1=value1 key2=value2". {emoji}'
            if exc.invalid_words:
                invalid_kw = ', '.join(exc.invalid_words)
                msg += f'\n  The following words violate this syntax:\n    {invalid_kw}'
            if isinstance(exc, EspeakKwargsConverterError):
                if exc.invalid_keys:
                    invalid_keys = ', '.join(exc.invalid_keys)
                    msg += f'\n  The following keys are not valid for {ctx.invoked_with}:\n    {invalid_keys}'
                if exc.invalid_values:
                    invalid_values = ', '.join(f'{k}={v}' for k, v in exc.invalid_values.items())
                    msg += f'\n  The following values are not understood for {ctx.invoked_with}:\n    {invalid_values}'
            await ctx.send(msg)

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

        self.logger.error(f'Ignoring exception in command {ctx.command}:')
        self.logger.error(''.join(tb))
        print(*tb)
