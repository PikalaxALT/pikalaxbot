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
