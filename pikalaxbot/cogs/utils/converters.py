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

import discord
from discord.ext import commands
import re
from .errors import BadGameArgument
from dateutil.relativedelta import relativedelta
import datetime
import asyncpg
import parsedatetime as pdt
import typing
import operator
from .. import *


__all__ = (
    'CommandConverter',
    'dice_roll',
    'AliasedRoleConverter',
    'board_coords',
    'espeak_params',
    'ShortTime',
    'HumanTime',
    'Time',
    'FutureTime',
    'PastTime',
    'ShortPastTime'
)


class CommandConverter(commands.Command):
    @classmethod
    async def convert(cls, ctx: MyContext, argument: str):
        cmd = ctx.bot.get_command(argument)
        if cmd is None:
            raise commands.CommandNotFound(argument)
        return cmd


def dice_roll(argument: str):
    match = re.match(r'(?P<count>\d+)?(d(?P<sides>\d+))?', argument)
    if match is None:
        raise ValueError
    count = int(match['count'] or 1)
    sides = int(match['sides'] or 6)
    assert 1 <= count <= 200 and 2 <= sides <= 100
    return count, sides


class AliasedRoleConverter(discord.Role):
    @classmethod
    async def convert(cls, ctx: MyContext, argument: str):
        async with ctx.bot.sql as sql:  # type: asyncpg.Connection
            role_id = await sql.fetchval(
                'select role_id '
                'from self_role '
                'where guild_id = $1 '
                'and alias = $2',
                ctx.guild.id,
                argument
            )
        if role_id is None:
            raise commands.RoleNotFound(f'No alias "{argument}" has been registered to a role')
        return await commands.RoleConverter().convert(ctx, role_id)


def board_coords(minx=1, maxx=5, miny=1, maxy=5):
    def real_converter(argument: typing.Union[str, tuple]):
        if isinstance(argument, tuple):
            return argument
        try:
            argument = argument.lower()
            if argument.startswith(tuple('abcde')):
                y = ord(argument[0]) - 0x60
                x = int(argument[1])
            else:
                y, x = map(int, argument.split())
            assert minx <= x <= maxx and miny <= y <= maxy
            return x - 1, y - 1
        except (ValueError, AssertionError, IndexError) as e:
            raise BadGameArgument from e
    return real_converter


def espeak_params(**valid_keys):
    def real_converter(argument: str):
        if isinstance(argument, str):
            # Convert from a string
            key, value = argument.split('=')
            value = valid_keys[key](value)
        else:
            # Make sure this is an iterable of length 2
            key, value = argument
        return key, value

    return real_converter


class ShortTime:
    compiled = re.compile("""(?:(?P<years>[0-9])(?:years?|y))?             # e.g. 2y
                             (?:(?P<months>[0-9]{1,2})(?:months?|mo))?     # e.g. 2months
                             (?:(?P<weeks>[0-9]{1,4})(?:weeks?|w))?        # e.g. 10w
                             (?:(?P<days>[0-9]{1,5})(?:days?|d))?          # e.g. 14d
                             (?:(?P<hours>[0-9]{1,5})(?:hours?|h))?        # e.g. 12h
                             (?:(?P<minutes>[0-9]{1,5})(?:minutes?|m))?    # e.g. 10m
                             (?:(?P<seconds>[0-9]{1,5})(?:seconds?|s))?    # e.g. 15s
                          """, re.VERBOSE)

    init_op = staticmethod(operator.add)

    def __init__(
            self,
            argument: str,
            *,
            now: datetime.datetime = None
    ):
        match = self.compiled.fullmatch(argument)
        if match is None or not match.group(0):
            raise commands.BadArgument('invalid time provided')

        data = {k: int(v) for k, v in match.groupdict(default='0').items()}
        now = now or datetime.datetime.utcnow()
        self.dt = self.init_op(now, relativedelta(**data))

    @classmethod
    async def convert(cls, ctx: MyContext, argument: str):
        return cls(argument, now=ctx.message.created_at)


class HumanTime:
    calendar = pdt.Calendar(version=pdt.VERSION_CONTEXT_STYLE)

    def __init__(self, argument: str, *, now: datetime.datetime = None):
        now = now or datetime.datetime.utcnow()
        dt, status = self.calendar.parseDT(argument, sourceTime=now)
        if not status.hasDateOrTime:
            raise commands.BadArgument('invalid time provided, try e.g. "tomorrow" or "3 days"')

        if not status.hasTime:
            # replace it with the current time
            dt = dt.replace(hour=now.hour, minute=now.minute, second=now.second, microsecond=now.microsecond)

        self.dt = dt
        self._past = dt < now

    @classmethod
    async def convert(cls, ctx: MyContext, argument: str):
        return cls(argument, now=ctx.message.created_at)


class Time(HumanTime):
    def __init__(self, argument: str, *, now: datetime.datetime = None):
        try:
            o = ShortTime(argument, now=now)
        except Exception as e:
            super().__init__(argument, now=now)
        else:
            self.dt = o.dt
            self._past = False


class FutureTime(Time):
    def __init__(self, argument: str, *, now: datetime.datetime = None):
        super().__init__(argument, now=now)

        if self._past:
            raise commands.BadArgument('this time is in the past')


class ShortPastTime(ShortTime):
    init_op = staticmethod(operator.sub)


class PastTime(HumanTime):
    def __init__(self, argument: str, *, now: datetime.datetime = None):
        try:
            o = ShortPastTime(argument, now=now)
        except Exception as e:
            super().__init__(argument, now=now)
        else:
            self.dt = o.dt
            self._past = True

        if not self._past:
            raise commands.BadArgument('That time is in the future')
