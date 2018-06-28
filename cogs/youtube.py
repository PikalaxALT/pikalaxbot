import asyncio
import discord
import youtube_dl
import ctypes.util
import traceback
from discord.client import log
from discord.ext import commands
from utils.botclass import PikalaxBOT
import subprocess
import os
import time
import re
from concurrent.futures import ThreadPoolExecutor


class cleaner_content(commands.clean_content):
    async def convert(self, ctx, argument):
        argument = await super().convert(ctx, argument)
        argument = re.sub(r'<a?:(\w+):\d+>', '\\1', argument)
        return argument


def check_ready(ctx):
    return ctx.command.instance.ready


def connected_and_not_playing(ctx):
    return ctx.voice_client.is_connected() and not ctx.voice_client.is_playing()


def call_espeak(msg, fname, **kwargs):
    args = ['espeak', '-w', fname]
    for flag, value in kwargs.items():
        dashes = '-' * (1 + (len(flag) > 1))
        args.extend([f'{dashes}{flag}', str(value)])
    args.append(msg)
    subprocess.check_call(args)


class EspeakAudioSource(discord.FFmpegPCMAudio):
    def __init__(self, bot, msg, *args, **kwargs):
        self.fname = f'tmp_{time.time()}.wav'
        call_espeak(msg, self.fname, **bot.espeak_kw)
        super().__init__(self.fname, *args, **kwargs)

    def cleanup(self):
        super().cleanup()
        if os.path.exists(self.fname):
            os.remove(self.fname)


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
        self.bot = bot
        self.ready = False
        self.connections = {}
        for executable in ('ffmpeg', 'avconv'):
            try:
                subprocess.check_call([executable, '-h'])
            except FileNotFoundError:
                continue
            self.ffmpeg = executable
            break
        else:
            raise discord.ClientException('ffmpeg or avconv not installed')
        self.executor = ThreadPoolExecutor()

    @staticmethod
    async def on_command_error(ctx, exc):
        if isinstance(ctx.cog, YouTube):
            tb = ''.join(traceback.format_exception_only(type(exc), exc))
            embed = discord.Embed(color=0xff0000)
            embed.add_field(name='Traceback', value=f'```{tb}```')
            await ctx.send(f'An error has occurred', embed=embed)

    async def on_ready(self):
        if self.load_opus():
            log.info('Loaded opus')
            for guild, chan in self.bot.voice_chans.items():
                ch = self.bot.get_channel(chan)
                if isinstance(ch, discord.VoiceChannel):
                    try:
                        await ch.connect()
                    except asyncio.TimeoutError:
                        log.error('Failed to connect to voice channel %s (connection timed out)', ch.name)
                    except discord.ClientException:
                        log.error('Failed to connect to voice channel %s (duplicate connection)', ch.name)
                    else:
                        log.info('Connected to voice channel %s', ch.name)

            self.ready = True

    @commands.group(pass_context=True)
    @commands.check(check_ready)
    # @commands.is_owner()
    async def pikavoice(self, ctx: commands.Context):
        """Commands for interacting with the bot in voice channels"""
        if ctx.invoked_subcommand is None:
            raise commands.CommandInvokeError('Invalid subcommand')

    @pikavoice.command()
    @commands.is_owner()
    async def chan(self, ctx: commands.Context, ch: discord.VoiceChannel):
        """Join a voice channel on the current server."""

        # All errors shall be communicated to the user, and also
        # passed to the bot's on_command_error handler.
        async with ctx.channel.typing():
            if ch is None:
                raise TypeError('Channel not found')
            if not ctx.me.permissions_in(ch).connect:
                raise discord.Forbidden(400, 'Insufficient permissions (Connect to voice channels)')
            if ch.guild != ctx.guild:
                raise TypeError('Guild mismatch')
            if ctx.guild.id in self.bot.voice_chans:
                if ch.id == self.bot.voice_chans[ctx.guild.id]:
                    raise ValueError('Already connected to that channel')
                vcl: discord.VoiceClient = ctx.guild.voice_client
                if vcl is None:
                    raise ValueError('Guild does not support voice connections')
                if vcl.is_connected():
                    await vcl.move_to(ch)
                else:
                    await ch.connect()
            else:
                await ch.connect()
            self.bot.voice_chans[ctx.guild.id] = ch.id
            self.bot.commit()
            await ctx.send('Joined the voice channel!')

    @pikavoice.command()
    @commands.check(connected_and_not_playing)
    async def say(self, ctx: commands.Context, *, msg: cleaner_content(fix_channel_mentions=True,
                                                                       escape_markdown=False)):
        """Use eSpeak to say the message aloud in the voice channel."""
        ctx.guild.voice_client.play(EspeakAudioSource(self.bot, msg, executable=self.ffmpeg,
                                                      before_options='-loglevel quiet'),
                                    after=lambda e: print('Player error: %s' % e) if e else None)

    @commands.command()
    async def pikasay(self, ctx, *, msg: cleaner_content(fix_channel_mentions=True,
                                                         escape_markdown=False)):
        """Use eSpeak to say the message aloud in the voice channel."""
        await ctx.invoke(self.say, msg=msg)

    @pikavoice.command()
    async def stop(self, ctx: commands.Context):
        """Stop all playing audio"""
        vclient: discord.VoiceClient = ctx.guild.voice_client
        if vclient.is_playing():
            vclient.stop()

    @commands.command()
    async def pikashutup(self, ctx):
        """Stop all playing audio"""
        await ctx.invoke(self.stop)

    @pikavoice.command()
    async def params(self, ctx, *, kwargs):
        """Update pikavoice params"""
        params = dict(self.bot.espeak_kw)
        invalid_keys = set()
        invalid_syntax = set()
        for word in kwargs.split():
            try:
                key, value = word.split('=')
                if key in 'agklpsv':
                    params[key] = value
                else:
                    invalid_keys.add(key)
            except ValueError:
                invalid_syntax.add(word)
        msg = ''
        if len(invalid_keys) > 0:
            msg += f'Invalid parameters: {", ".join(invalid_keys)}\n'
        if len(invalid_syntax) > 0:
            msg += f'Invalid syntax: {", ".join(invalid_syntax)}\n'
        if len(msg) > 0:
            raise KeyError(msg)
        try:
            call_espeak('Test', 'tmp.wav', **params)
        except subprocess.CalledProcessError:
            await ctx.send('Parameters could not be updated')
        else:
            self.bot.espeak_kw = params
            self.bot.commit()
            await ctx.send('Parameters successfully updated')
        finally:
            os.remove('tmp.wav')

    @commands.command()
    async def pikaparams(self, ctx, *, kwargs):
        """Update pikavoice params"""
        await ctx.invoke(self.params, kwargs=kwargs)


def setup(bot: PikalaxBOT):
    bot.add_cog(YouTube(bot))


def teardown(bot: PikalaxBOT):
    for vc in bot.voice_clients: # type: discord.VoiceClient
        asyncio.ensure_future(vc.disconnect(), loop=bot.loop)
