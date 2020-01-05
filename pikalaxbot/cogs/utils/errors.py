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


class NotInitialized(Exception):
    pass


class AlreadyInitialized(Exception):
    pass


class InitializationInvalid(Exception):
    pass


class ReactionAlreadyRegistered(Exception):
    pass


class RoleOrEmojiNotFound(Exception):
    pass


class NotReady(commands.CheckFailure):
    pass


class BotIsIgnoringUser(commands.CheckFailure):
    pass


class CogOperationError(commands.CommandError):
    def __init__(self, mode, **kwargs):
        super().__init__()
        self.mode = mode
        self.cog_errors = kwargs
