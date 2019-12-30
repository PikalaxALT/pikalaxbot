import asyncio
import twitchio
from twitchio.ext import commands


__all__ = (
    'TwitchBot',
    'create_twitch_bot'
)


class TwitchBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        self._discord_bot = kwargs.pop('discord_bot', None)
        super().__init__(*args, **kwargs)

    def dpy_dispatch(self, event, *args, **kwargs):
        """Dispatch an event to the d.py bot. The reactor will be
        a coroutine function f'on_{event}' taking (*args, **kwargs)."""
        self._discord_bot.dispatch(event, *args, **kwargs)


def create_twitch_bot(dpy_bot):
    settings = dpy_bot.settings
    try:
        bot = TwitchBot(
            discord_bot=dpy_bot,
            irc_token=settings.twitch_token,
            client_id=settings.twitch_client,
            nick=settings.twitch_nick,
            prefix=settings.prefix,
            initial_channels=settings.irc_channels,
            loop=dpy_bot.loop
        )
    except AttributeError:
        required_attrs = (
            'twitch_token',
            'twitch_client',
            'twitch_nick',
            'prefix',
            'irc_channels'
        )
        missing_attrs = ', '.join(attr for attr in required_attrs if attr not in settings)

        async def report_twitch_error():
            await dpy_bot.wait_until_ready()
            await dpy_bot.exc_channel.send(f'Missing settings requred for Twitch bot: {missing_attrs}')

        dpy_bot.loop.create_task(report_twitch_error())
        return None

    @bot.event
    async def event_ready():
        print('Logged in to Twitch')

    @bot.command()
    async def test(ctx: twitchio.Context):
        await ctx.send('This is a test. This is only a test.')

    @bot.event
    async def event_dpy_say(ctx, channel, message):
        channel = bot.get_channel(channel)
        await channel.send(f'{ctx.author.name} ({ctx.guild}!{ctx.channel}) says: {message}')

    bot.loop.create_task(bot.start())
    return bot
