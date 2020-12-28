import discord
from discord.ext import commands
import re
import random
import typing


__all__ = ('MyContext',)


def case_repl(*repls):
    if len(repls) == 1:
        repls, = repls
    def inner(match):
        ret = ''
        for x, y in zip(match[0], repls):
            if isinstance(y, str):
                y = [y, y.upper()]
            ret += y[x.isupper()]
        return ret
    return inner


OWO_REPL = {
  re.compile('er', re.I): case_repl('ew'),
  re.compile('l', re.I): case_repl('w'),
  re.compile('the', re.I): case_repl('t', 'h', ['uwu', 'UwU']),
  re.compile('row', re.I): lambda m: m[0] + 'oO'[m[0][1].isupper()],
  re.compile('rus', re.I): case_repl('r', ['uwu', 'UwU'], 's')
}


def owoify_message(text: str):
    [text := pat.sub(repl, text) for pat, repl in OWO_REPL.items()]
    return text + random.choice(['owo', 'uwu', 'OwO', 'UwU'])


class MyContext(commands.Context):
    async def send(self, content: typing.Optional[str] = None, **kwargs):
        if content is not None:
            content = owoify_message(content)
        return await super().send(content, **kwargs)
