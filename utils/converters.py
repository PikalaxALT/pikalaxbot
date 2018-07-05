import asyncio
import discord
from discord.ext import commands


class KwargConverterError(commands.BadArgument):
    def __init__(self, argument):
        self.invalid_words = set()
        testdict = {}
        for word in argument.split():
            try:
                key, value = word.split('=')
                testdict[key] = value
            except (ValueError, TypeError):
                self.invalid_words.add(word)
        super().__init__('Invalid syntax for KwargConverter')


class KwargConverter(commands.Converter):
    async def convert(self, ctx, argument) -> dict:
        """Converts a list of key=value words to a dict {key: value}.
        Returns: dict
        Raises: KwargConverterError, if any word cannot be parsed as described.
        """
        try:
            return dict(word.split('=') for word in argument.split())
        except (ValueError, TypeError) as e:
            raise KwargConverterError(argument)


class EspeakKwargsConverterError(KwargConverterError):
    def __init__(self, argument, invalid_keys, invalid_values):
        super().__init__(argument)
        self.invalid_keys = invalid_keys
        self.invalid_values = invalid_values


class EspeakKwargsConverter(KwargConverter):
    async def convert(self, ctx, argument):
        kwargs = await super().convert(ctx, argument)
        invalid_keys = []
        invalid_values = {}
        for key, value in kwargs.items():
            if key in tuple('agkpsv'):
                if key != 'v':
                    try:
                        kwargs[key] = int(value)
                    except ValueError:
                        invalid_values[key] = value
            else:
                invalid_keys.append(key)
        if invalid_keys or invalid_values:
            raise EspeakKwargsConverterError(argument, invalid_keys, invalid_values)
        return kwargs
