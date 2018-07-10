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

from utils.botclass import PikalaxBOT


class Cog:
    config_attrs = tuple()

    def __init__(self, bot):
        self.bot: PikalaxBOT = bot
        self.fetch()

    def __del__(self):
        self.commit()

    def fetch(self):
        with self.bot.settings as settings:
            for attr in self.config_attrs:
                val = getattr(settings.user, attr)
                if isinstance(val, list):
                    val = set(val)
                setattr(self, attr, val)

    def commit(self):
        with self.bot.settings as settings:
            for attr in self.config_attrs:
                val = getattr(self, attr)
                if isinstance(val, set):
                    val = list(val)
                setattr(settings.user, attr, val)
