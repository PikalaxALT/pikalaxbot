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
import typing


__all__ = ('MaybeEmoji', 'T', 'R', 'EmbedStr', 'MaybePartialEmoji')


T = typing.TypeVar('T')
R = typing.TypeVar('R')
EmbedStr = typing.Union[str, type(discord.Embed.Empty)]
MaybeEmoji = typing.Union[discord.Emoji, discord.PartialEmoji, str]
MaybePartialEmoji = typing.Union[discord.PartialEmoji, str]
