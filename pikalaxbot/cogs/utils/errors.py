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
