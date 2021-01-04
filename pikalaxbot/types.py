import discord
import typing


__all__ = ('MaybeEmoji', 'T', 'R', 'EmbedStr', 'MaybePartialEmoji')


T = typing.TypeVar('T')
R = typing.TypeVar('R')
EmbedStr = typing.Union[str, discord.Embed.Empty]
MaybeEmoji = typing.Union[discord.Emoji, discord.PartialEmoji, str]
MaybePartialEmoji = typing.Union[discord.PartialEmoji, str]
