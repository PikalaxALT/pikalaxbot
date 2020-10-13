import discord
from discord.ext import commands
import re
from .errors import BadGameArgument
from dateutil.relativedelta import relativedelta
import datetime
import parsedatetime as pdt


__all__ = (
    'CommandConverter',
    'DiceRollConverter',
    'AliasedRoleConverter',
    'BoardCoords',
    'EspeakParamsConverter',
    'ShortTime',
    'HumanTime',
    'Time',
    'FutureTime'
)


class CommandConverter(commands.Converter):
    async def convert(self, ctx: commands.Context, argument):
        cmd = ctx.bot.get_command(argument)
        if cmd is None:
            raise commands.CommandNotFound(argument)
        return cmd


class DiceRollConverter(commands.Converter):
    _pattern = re.compile(r'(?P<count>\d+)?(d(?P<sides>\d+))?')

    async def convert(self, ctx, argument):
        match = self._pattern.match(argument)
        if match is None:
            raise ValueError
        count = int(match['count'] or 1)
        sides = int(match['sides'] or 6)
        assert 1 <= count <= 200 and 2 <= sides <= 100
        return count, sides


class AliasedRoleConverter(commands.Converter):
    async def convert(self, ctx, argument):
        role_id = ctx.cog.roles.get(str(ctx.guild.id), {}).get(argument.lower())
        if role_id is None:
            raise commands.BadArgument(f'No alias "{argument}" has been registered to a role')
        return discord.utils.get(ctx.guild.roles, id=role_id)


class BoardCoords(commands.Converter):
    def __init__(self, minx=1, maxx=5, miny=1, maxy=5):
        super().__init__()
        self.minx = minx
        self.maxx = maxx
        self.miny = miny
        self.maxy = maxy

    async def convert(self, ctx, argument):
        if isinstance(argument, tuple):
            return argument
        try:
            argument = argument.lower()
            if argument.startswith(tuple('abcde')):
                y = ord(argument[0]) - 0x60
                x = int(argument[1])
            else:
                y, x = map(int, argument.split())
            assert self.minx <= x <= self.maxx and self.miny <= y <= self.maxy
            return x - 1, y - 1
        except (ValueError, AssertionError) as e:
            raise BadGameArgument from e


class EspeakParamsConverter(commands.Converter):
    def __init__(self, **valid_keys):
        """Converts key=value pairs to a 2ple
        valid_keys: name=type pairs
        """
        super().__init__()
        self.valid_keys = valid_keys

    async def convert(self, ctx, argument):
        if isinstance(argument, str):
            # Convert from a string
            key, value = argument.split('=')
            value = self.valid_keys[key](value)
        else:
            # Make sure this is an iterable of length 2
            key, value = argument
        return key, value


# Thanks Danny#0007/Rapptz for these handy converters
class ShortTime:
    compiled = re.compile("""(?:(?P<years>[0-9])(?:years?|y))?             # e.g. 2y
                             (?:(?P<months>[0-9]{1,2})(?:months?|mo))?     # e.g. 2months
                             (?:(?P<weeks>[0-9]{1,4})(?:weeks?|w))?        # e.g. 10w
                             (?:(?P<days>[0-9]{1,5})(?:days?|d))?          # e.g. 14d
                             (?:(?P<hours>[0-9]{1,5})(?:hours?|h))?        # e.g. 12h
                             (?:(?P<minutes>[0-9]{1,5})(?:minutes?|m))?    # e.g. 10m
                             (?:(?P<seconds>[0-9]{1,5})(?:seconds?|s))?    # e.g. 15s
                          """, re.VERBOSE)

    def __init__(self, argument, *, now=None):
        match = self.compiled.fullmatch(argument)
        if match is None or not match.group(0):
            raise commands.BadArgument('invalid time provided')

        data = { k: int(v) for k, v in match.groupdict(default=0).items() }
        now = now or datetime.datetime.utcnow()
        self.dt = now + relativedelta(**data)

    @classmethod
    async def convert(cls, ctx, argument):
        return cls(argument, now=ctx.message.created_at)


class HumanTime:
    calendar = pdt.Calendar(version=pdt.VERSION_CONTEXT_STYLE)

    def __init__(self, argument, *, now=None):
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
    async def convert(cls, ctx, argument):
        return cls(argument, now=ctx.message.created_at)


class Time(HumanTime):
    def __init__(self, argument, *, now=None):
        try:
            o = ShortTime(argument, now=now)
        except Exception as e:
            super().__init__(argument, now=now)
        else:
            self.dt = o.dt
            self._past = False


class FutureTime(Time):
    def __init__(self, argument, *, now=None):
        super().__init__(argument, now=now)

        if self._past:
            raise commands.BadArgument('this time is in the past')
