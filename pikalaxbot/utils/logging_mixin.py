# PikalaxBOT - A Discord bot in discord.py
# Copyright (C) 2018-2021  PikalaxALT
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
import typing
import os
import sys
from ..context import *


__all__ = ('LoggingMixin', 'BotLogger')


class LoggingMixin:
    def __init__(self, *args, **kwargs):
        self.logger = logging.getLogger('discord')
        super().__init__(*args, **kwargs)

    def log_info(self, msg: str, *args, **kwargs):
        self.logger.log(logging.INFO, msg, *args, **kwargs)

    def log_debug(self, msg: str, *args, **kwargs):
        self.logger.log(logging.DEBUG, msg, *args, **kwargs)

    def log_warning(self, msg: str, *args, **kwargs):
        self.logger.log(logging.WARNING, msg, *args, **kwargs)

    def log_error(self, msg: str, *args, **kwargs):
        self.logger.log(logging.ERROR, msg, *args, **kwargs)

    def log_critical(self, msg: str, *args, **kwargs):
        self.logger.log(logging.CRITICAL, msg, *args, **kwargs)

    def log_tb(self, ctx: typing.Union[MyContext, FakeContext, None], exc: BaseException):
        self.log_error(
            f'Ignoring exception in command {ctx.command}:' if ctx else '',
            exc_info=(exc.__class__, exc, exc.__traceback__)
        )


class BotLogger(LoggingMixin):
    def __init__(
            self,
            *,
            logfile: typing.Union[str, os.PathLike],
            log_level=logging.NOTSET,
            log_stderr=True,
            **kwargs
    ):
        super().__init__(**kwargs)
        self.logger.setLevel(log_level)
        fmt = logging.Formatter('%(asctime)s (PID:%(process)s) - %(levelname)s - %(message)s')
        if logfile:
            handler = logging.FileHandler(logfile, mode='w')
            handler.setFormatter(fmt)
            self.logger.addHandler(handler)
        if log_stderr:
            handler = logging.StreamHandler(sys.stderr)
            handler.setFormatter(fmt)
            self.logger.addHandler(handler)
