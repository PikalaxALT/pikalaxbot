import asyncio
import twitchio
from twitchio.ext import commands


class TwitchBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._discord_bot = None


def launch_twitch_bot(token, client, nick, channels):
    bot = TwitchBot(irc_token=token, client_id=client, nick=nick, prefix='p!', initial_channels=channels)

    @bot.event
    async def event_ready():
        print('Logged in to Twitch')

    @bot.command()
    async def test(ctx: twitchio.Context):
        await ctx.send('This is a test. This is only a test.')

    asyncio.create_task(bot.start())
    return bot
