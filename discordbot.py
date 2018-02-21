import asyncio
from discord import Client


if __name__ == '__main__':
    raise EnvironmentError('This file cannot be executed from the command '
                           'line. It may only be imported.')


class DiscordBot(Client):
    ...

bot = DiscordBot()


@bot.event
async def on_ready():
    ...


@bot.event
async def on_message(message):
    ...
