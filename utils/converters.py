import asyncio
import discord
from discord.ext import commands


class KwargConverterError(commands.CommandError):
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
        try:
            return dict(word.split('=') for word in argument.split())
        except (ValueError, TypeError) as e:
            raise KwargConverterError(argument)
