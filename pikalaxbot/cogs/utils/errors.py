from discord.ext import commands


__all__ = (
    'BadGameArgument',
    'CommandBannedInGuild',
    'NotEnoughOptions',
    'TooManyOptions',
    'ReactionIntegrityError',
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


class NotEnoughOptions(ValueError):
    pass


class TooManyOptions(ValueError):
    pass


class ReactionIntegrityError(ValueError):
    pass


class NotPollOwner(ValueError):
    pass


class NoPollFound(KeyError):
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
