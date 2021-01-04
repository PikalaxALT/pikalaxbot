import discord
from discord.ext import commands, menus
import typing
import os
import logging
import asyncpg
import aiohttp
import asyncio
import datetime
import traceback
from .utils.logging_mixin import LoggingMixin
from .context import MyContext, FakeContext
from .utils.config_io import Settings
if typing.TYPE_CHECKING:
    from .ext.pokeapi import PokeApi


__all__ = ('PikalaxBOT',)


class PikalaxBOT(LoggingMixin, commands.Bot):
    def __init__(
            self,
            settings_file: typing.Union[str, os.PathLike],
            logfile: typing.Union[str, os.PathLike],
            **kwargs
    ):
        # Load settings
        log_level = kwargs.pop('log_level', logging.NOTSET)
        self.settings = Settings(settings_file)
        super().__init__(activity=discord.Game(self.settings.game), **kwargs)
        self._ctx_cache = {}
        self.guild_prefixes = {}
        self._sql = 'postgres://{username}:{password}@{host}/{dbname}'.format(**self.settings.database)

        # Set up logger
        self.logger.setLevel(log_level)
        handler = logging.FileHandler(logfile, mode='w')
        fmt = logging.Formatter('%(asctime)s (PID:%(process)s) - %(levelname)s - %(message)s')
        handler.setFormatter(fmt)
        self.logger.addHandler(handler)

        async def init_client_session():
            self.client_session = aiohttp.ClientSession()
            try:
                self._pool = await asyncpg.create_pool(self._sql)
            except Exception:
                await self.client_session.close()
                raise

        self.log_info('Creating aiohttp session')
        self.client_session: typing.Optional[aiohttp.ClientSession] = None
        self._pool: typing.Optional[asyncpg.pool.Pool] = None
        self.loop.run_until_complete(init_client_session())

        # Reboot handler
        self.reboot_after = True

        self._alive_since: typing.Optional[datetime.datetime] = None
        self._pokeapi_factory: typing.Optional[typing.Callable[[], 'PokeApi']] = None
        self._pokeapi: typing.Optional['PokeApi'] = None

    @property
    def exc_channel(self):
        try:
            return self.get_channel(self.settings.exc_channel)
        except AttributeError:
            return None

    @property
    def command_error_emoji(self):
        return discord.utils.get(self.emojis, name=self.settings.error_emoji)

    @property
    def sql(self):
        return self._pool.acquire()

    @property
    def pokeapi(self) -> typing.Optional['PokeApi']:
        return self._pokeapi

    @pokeapi.setter
    def pokeapi(self, value: typing.Optional['PokeApi']):
        self._pokeapi = value

    async def send_tb(
            self,
            ctx: typing.Optional[MyContext],
            exc: BaseException,
            *,
            origin: typing.Optional[str] = None,
            embed: typing.Optional[discord.Embed] = None
    ):
        msg = f'Ignoring exception in {origin}' if origin is not None else ''
        channel = self.exc_channel
        if channel is None:
            return
        if ctx is None:
            if self.owner_id is None:
                await self.is_owner(discord.Object(id=0))
            ctx = FakeContext(channel.guild, channel, None, channel.guild.get_member(self.owner_id))
        paginator = commands.Paginator()
        msg and paginator.add_line(msg)
        for line in traceback.format_exception(exc.__class__, exc, exc.__traceback__):
            paginator.add_line(line.rstrip('\n'))
        self.log_error(msg, exc_info=(exc.__class__, exc, exc.__traceback__))

        class TracebackPageSource(menus.ListPageSource):
            def format_page(self, menu: menus.MenuPages, page: str):
                return {'content': page, 'embed': embed}

        menu_ = menus.MenuPages(TracebackPageSource(paginator.pages, per_page=1))
        await menu_.start(ctx, channel=channel)

    def run(self):
        self.log_info('Starting bot')
        token = self.settings.token
        super().run(token)

    async def close(self):
        self.log_info('Logout request receeived')
        await asyncio.gather(*(client.disconnect(force=True) for client in self.voice_clients), return_exceptions=True)
        try:
            await super().close()
        finally:
            await self.client_session.close()
            await self._pool.close()

    async def on_ready(self):
        self.log_info(f'Logged in as {self.user}')

    async def get_context(self, message, *, cls=None) -> MyContext:
        ctx = await super().get_context(message, cls=cls or MyContext)
        self._ctx_cache[(message.channel.id, message.id)] = [ctx, set()]
        return ctx
