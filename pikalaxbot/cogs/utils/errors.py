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

from discord.ext import commands


__all__ = (
    'BadGameArgument',
    'CommandBannedInGuild',
    'NotEnoughOptions',
    'TooManyOptions',
    'NotPollOwner',
    'NoPollFound',
    'NotInitialized',
    'AlreadyInitialized',
    'ReactionAlreadyRegistered',
    'RoleOrEmojiNotFound',
    'InitializationInvalid',
    'NotReady',
    'BotIsIgnoringUser',
    'CogOperationError'
)


class BadGameArgument(commands.BadArgument):
    pass


class CommandBannedInGuild(commands.CheckFailure):
    pass


class NotEnoughOptions(commands.BadArgument):
    pass


class TooManyOptions(commands.BadArgument):
    pass


class NotPollOwner(commands.CheckFailure):
    pass


class NoPollFound(commands.CheckFailure):
    pass


class NotInitialized(commands.CheckFailure):
    pass


class AlreadyInitialized(commands.CheckFailure):
    pass


class InitializationInvalid(commands.CommandError):
    pass


class ReactionAlreadyRegistered(commands.CommandError):
    pass


class RoleOrEmojiNotFound(commands.CommandError):
    pass


class NotReady(commands.CheckFailure):
    pass


class BotIsIgnoringUser(commands.CheckFailure):
    pass


class CogOperationError(commands.CommandError):
    def __init__(self, mode, **kwargs):
        super().__init__(message=f'{mode}ing {len(kwargs)} extension(s) failed')
        self.mode = mode
        self.cog_errors = kwargs
