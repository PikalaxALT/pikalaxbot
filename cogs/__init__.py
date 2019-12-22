# PikalaxBOT - A Discord bot in discord.py
# Copyright (C) 2018  PikalaxALT
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import aiohttp
import typing

from discord.ext import commands
from utils.botclass import PikalaxBOT, LoggingMixin


class BaseCog(LoggingMixin, commands.Cog):
    """
    Base class for all cog files.  Inherits :class:LoggingMixin

    __init__ params:
        bot: PikalaxBOT - The instance of the bot.

    Attributes:
        config_attrs: tuple - Names of attributes to fetch from the bot's
        settings.  When subclassing BaseCog, define this at the class level.
    """
    config_attrs: typing.Tuple[str] = tuple()

    def __init__(self, bot: PikalaxBOT):
        super().__init__()
        self.bot: PikalaxBOT = bot
        self.fetch()

    def fetch(self):
        """
        Loads local attributes from the bot's settings
        """
        self.log_debug(f'Fetching {self.__class__.__name__}')
        for attr in self.config_attrs:
            self.log_debug(attr)
            try:
                val = getattr(self.bot.settings, attr)
            except AttributeError:
                continue
            if isinstance(val, list):
                val = set(val)
            setattr(self, attr, val)

    async def commit(self):
        """
        Commits local attributes to the bot's settings file
        """
        async with self.bot.settings as settings:
            for attr in self.config_attrs:
                self.log_debug(attr)
                val = getattr(self, attr)
                if isinstance(val, set):
                    val = list(val)
                setattr(settings, attr, val)

    @property
    def cs(self) -> aiohttp.ClientSession:
        """The client session attached to the cog"""
        return self.bot.user_cs

    @cs.setter
    def cs(self, value: aiohttp.ClientSession):
        self.bot.user_cs = value

    async def hastebin(self, content: str) -> str:
        """Upload the content to hastebin and return the url.

        :param content: str: Raw content to upload
        :return: str: URL to the uploaded content
        :raises aiohttp.ClientException: on failure to upload
        """
        self.bot.ensure_client_session()
        res = await self.cs.post('https://hastebin.com/documents', data=content.encode('utf-8'))
        post = await res.json()
        uri = post['key']
        return f'https://hastebin.com/{uri}'
