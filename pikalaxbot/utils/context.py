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
    re.compile('row', re.I): lambda m: m[0][:2] + 'w' + m[0][1],
    re.compile('rus', re.I): case_repl('r', ['uwu', 'UwU'], 's')
}


def owoify_message(text: str):
    [text := pat.sub(repl, text) for pat, repl in OWO_REPL.items()]
    return text + ' ' + random.choice(['owo', 'uwu', 'OwO', 'UwU'])


def owoify_embed(embed: discord.Embed):
    if embed.title is not embed.Empty:
        embed.title = owoify_message(embed.title)
    if embed.description is not embed.Empty:
        embed.description = owoify_message(embed.description)
    for i, field in enumerate(embed.fields):
        embed.set_field_at(
            i,
            name=owoify_message(field.name),
            value=owoify_message(field.value),
            inline=field.inline
        )
    if embed.footer.text is not embed.Empty:
        embed.set_footer(
            text=owoify_message(embed.footer.text),
            icon_url=embed.footer.icon_url
        )
    if embed.author.name is not embed.Empty:
        embed.set_author(
            name=owoify_message(embed.author.name),
            url=embed.author.url,
            icon_url=embed.author.icon_url
        )
    return embed


class MyContext(commands.Context):
    async def send(self, content: typing.Optional[str] = None, **kwargs):
        if content is not None:
            content = owoify_message(str(content))

        try:
            embed = kwargs.pop('embed')  # type: typing.Optional[discord.Embed]
        except KeyError:
            pass
        else:
            if embed is not None:
                embed = owoify_embed(embed)
            kwargs['embed'] = embed

        return await super().send(content, **kwargs)

    async def reply(self, content: typing.Optional[str] = None, **kwargs):
        if content is not None:
            content = owoify_message(str(content))

        try:
            embed = kwargs.pop('embed')  # type: typing.Optional[discord.Embed]
        except KeyError:
            pass
        else:
            if embed is not None:
                embed = owoify_embed(embed)
            kwargs['embed'] = embed

        return await super().reply(content, **kwargs)
