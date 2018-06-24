import asyncio
import discord
import youtube_dl
import ctypes.util
import traceback
from discord.client import log
from discord.ext import commands
from utils.botclass import PikalaxBOT


class EspeakAudioSource(discord.AudioSource):
    def __init__(self, msg):
        self.msg = msg

    async def __aenter__(self):
        ...

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        ...


class YouTube:
    @staticmethod
    def load_opus():
        if not discord.opus.is_loaded():
            opus_name = ctypes.util.find_library('libopus')
            if opus_name is None:
                log.error('Failed to find the Opus library.')
            else:
                discord.opus.load_opus(opus_name)
        return discord.opus.is_loaded()

    def __init__(self, bot: PikalaxBOT):
        async def init():
            await bot.wait_until_ready()
            for guild, chan in bot.voice_chans.items():
                ch = bot.get_channel(chan)
                if isinstance(ch, discord.VoiceChannel):
                    try:
                        await ch.connect()
                    except asyncio.TimeoutError:
                        log.error('Failed to connect to voice channel %s (connection timed out)', ch.name)
                        continue
                    except discord.ClientException:
                        log.error('Failed to connect to voice channel %s (duplicate connection)', ch.name)
                        continue

            self.ready = True

        self.bot = bot
        self.ready = False
        self.connections = {}
        if self.load_opus():
            asyncio.ensure_future(init(), loop=bot.loop)

    async def check_ready(self, ctx):
        return self.ready

    @commands.group(pass_context=True)
    @commands.check(check_ready)
    async def pikavoice(self, ctx):
        """Commands for interacting with the bot in voice channels"""

    @pikavoice.command()
    async def chan(self, ctx: commands.Context, ch: discord.VoiceChannel):
        """Join a voice channel on the current server."""

        # All errors shall be communicated to the user, and also
        # passed to the bot's on_command_error handler.
        try:
            if ch is None:
                raise TypeError('Channel not found')
            if ch.guild != ctx.guild:
                raise TypeError('Guild mismatch')
            if ctx.guild.id in self.bot.voice_chans:
                if ch.id == self.bot.voice_chans[ctx.guild.id]:
                    raise ValueError('Already connected to that channel')
                vcl = ctx.guild.voice_client  # type: discord.VoiceClient
                await vcl.move_to(ch)
            else:
                await ch.connect()
            self.bot.voice_chans[ctx.guild.id] = ch.id
        except Exception as e:
            tb = traceback.format_exc(limit=0)
            await ctx.send(f'An error has occurred: {tb}')
            raise commands.CommandError from e

    @pikavoice.command()
    async def say(self, ctx: commands.Context, *, msg):
        """Use eSpeak to say the message aloud in the voice channel."""
        raise NotImplemented


def setup(bot: PikalaxBOT):
    bot.add_cog(YouTube(bot))


def teardown(bot: PikalaxBOT):
    for vc in bot.voice_clients: # type: discord.VoiceClient
        asyncio.ensure_future(vc.disconnect(), loop=bot.loop)
