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

import logging
from utils.botclass import PikalaxBOT, LoggingMixin


class Cog(LoggingMixin):
    config_attrs = tuple()

    def __init__(self, bot):
        super().__init__()
        self.bot: PikalaxBOT = bot
        self.fetch()

    def fetch(self):
        self.log_debug(f'Fetching {self.__class__.__name__}')
        for attr in self.config_attrs:
            self.log_debug(attr)
            val = getattr(self.bot.settings, attr)
            if isinstance(val, list):
                val = set(val)
            setattr(self, attr, val)

    def commit(self):
        with self.bot.settings as settings:
            for attr in self.config_attrs:
                self.log_debug(attr)
                val = getattr(self, attr)
                if isinstance(val, set):
                    val = list(val)
                setattr(settings, attr, val)

    async def __before_invoke(self, ctx):
        self.fetch()
        if self.bot.settings.debug:
            owner = self.bot.get_user(self.bot.owner_id)
            await owner.send(f'before_invoke: {self.__class__.__name__}.{ctx.command}')

    async def __after_invoke(self, ctx):
        self.commit()
        if self.bot.settings.debug:
            owner = self.bot.get_user(self.bot.owner_id)
            await owner.send(f'after_invoke: {self.__class__.__name__}.{ctx.command}')
