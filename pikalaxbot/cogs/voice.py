# PikalaxBOT - A Discord bot in discord.py
# Copyright (C) 2018  PikalaxALT
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import asyncio
import discord
import ctypes.util
from discord.ext import commands
from . import BaseCog
import subprocess
import os
import time
import re
from .utils.converters import EspeakParamsConverter


class VoiceCommandError(commands.CheckFailure):
    """This is raised when an error occurs in a voice command."""


class cleaner_content(commands.clean_content):
    async def convert(self, ctx, argument):
        argument = await super().convert(ctx, argument)
        argument = re.sub(r'<a?:(\w+):\d+>', '\\1', argument)
        return argument


def voice_client_not_playing(ctx):
    # Change: Don't care anymore if the voice client exists or is playing.
    vc = ctx.voice_client
    return vc is None or not vc.is_playing()


async def voice_cmd_ensure_connected(ctx):
    vc: discord.VoiceClient = ctx.voice_client
    if vc is None or not vc.is_connected():
        if ctx.author.voice is None:
            raise VoiceCommandError('Invoker is not connected to voice')
        vchan = ctx.author.voice.channel
        if not vchan.permissions_for(ctx.guild.me).connect:
            raise VoiceCommandError('I do not have permission to connect to the voice channel '
                                    'configured for this guild')
        await vchan.connect()
    return True


class EspeakAudioSource(discord.FFmpegPCMAudio):
    def __init__(self, fname, **kwargs):
        super().__init__(fname, **kwargs)
        self.fname = fname

    @staticmethod
    async def call_espeak(msg, fname, *, loop=None, **kwargs):
        flags = ' '.join(f'-{flag} {value}' for flag, value in kwargs.items())
        msg = msg.replace('"', '\\"')
        args = f'espeak -w {fname} {flags} "{msg}"'
        fut = await asyncio.create_subprocess_shell(args, loop=loop, stderr=-1, stdout=-1)
        out, err = await fut.communicate()
        if fut.returncode != 0:
            raise subprocess.CalledProcessError(fut.returncode, args, out, err)

    @classmethod
    async def from_message(cls, cog, msg, **kwargs):
        fname = f'{os.getcwd()}/{time.time()}.wav'
        await cls.call_espeak(msg, fname, loop=cog.bot.loop, **cog.espeak_kw)
        return cls(fname, **kwargs)

    def cleanup(self):
        super().cleanup()
        if os.path.exists(self.fname):
            os.remove(self.fname)


class Voice(BaseCog):
    __ffmpeg_options = {
        'before_options': '-loglevel error',
        'options': '-vn'
    }
    espeak_kw = {}
    config_attrs = 'espeak_kw',
    __espeak_valid_keys = {
        'a': int,
        's': int,
        'v': str,
        'p': int,
        'g': int,
        'k': int
    }

    def __init__(self, bot):
        super().__init__(bot)
        self.load_opus()

        with open(os.devnull, 'w') as DEVNULL:
            for executable in ('ffmpeg', 'avconv'):
                try:
                    subprocess.run([executable, '-h'], stdout=DEVNULL, stderr=DEVNULL, check=True)
                except FileNotFoundError:
                    continue
                self.ffmpeg = executable
                self.__ffmpeg_options['executable'] = executable
                break
            else:
                raise discord.ClientException('ffmpeg or avconv not installed')
        self.timeout_tasks = {}

    @staticmethod
    async def idle_timeout(ctx):
        await asyncio.sleep(600)
        await ctx.voice_client.disconnect()

    def start_timeout(self, ctx):
        def done(unused):
            self.timeout_tasks.pop(ctx.guild.id, None)

        task = self.bot.loop.create_task(Voice.idle_timeout(ctx))
        task.add_done_callback(done)
        self.timeout_tasks[ctx.guild.id] = task

    def player_after(self, ctx, exc):
        if exc:
            ctx.bot.dispatch('command_error', ctx, exc)
            print(f'Player error: {exc}')
        self.start_timeout(ctx)

    def load_opus(self):
        if not discord.opus.is_loaded():
            opus_name = ctypes.util.find_library('libopus')
            if opus_name is None:
                self.log_error('Failed to find the Opus library.')
            else:
                discord.opus.load_opus(opus_name)
        return discord.opus.is_loaded()

    @commands.group(name='voice')
    async def pikavoice(self, ctx: commands.Context):
        """Commands for interacting with the bot in voice channels"""
        if ctx.invoked_subcommand is None:
            raise commands.CommandInvokeError('Invalid subcommand')

    @commands.check(voice_cmd_ensure_connected)
    @commands.check(voice_client_not_playing)
    @pikavoice.command()
    async def say(self, ctx: commands.Context, *, msg: cleaner_content(fix_channel_mentions=True,
                                                                       escape_markdown=False)):
        """Use eSpeak to say the message aloud in the voice channel."""
        msg = f'{ctx.author.display_name} says: {msg}'
        try:
            player = await EspeakAudioSource.from_message(self, msg, **self.__ffmpeg_options)
        except subprocess.CalledProcessError:
            return await ctx.send('Error saying shit')
        ctx.voice_client.play(player, after=lambda exc: self.player_after(ctx, exc))

    @commands.check(voice_cmd_ensure_connected)
    @commands.check(voice_client_not_playing)
    @commands.command(name='say')
    async def pikasay(self, ctx, *, msg: cleaner_content(fix_channel_mentions=True,
                                                         escape_markdown=False)):
        """Use eSpeak to say the message aloud in the voice channel."""
        await ctx.invoke(self.say, msg=msg)

    @pikavoice.command()
    async def stop(self, ctx: commands.Context):
        """Stop all playing audio"""
        vclient: discord.VoiceClient = ctx.voice_client
        if vclient.is_playing():
            vclient.stop()

    @commands.command()
    async def shutup(self, ctx):
        """Stop all playing audio"""
        await ctx.invoke(self.stop)

    @pikavoice.command()
    async def params(self, ctx, *kwargs: EspeakParamsConverter(**__espeak_valid_keys)):
        """Update pikavoice params.

        Syntax: p!params a=amplitude g=gap k=emphasis p=pitch s=speed v=voice"""
        params = dict(self.espeak_kw)
        for key, value in kwargs:
            params[key] = (str if key == 'v' else int)(value)
        try:
            await EspeakAudioSource.call_espeak('Test', 'tmp.wav', **params)
        except subprocess.CalledProcessError:
            await ctx.send('Parameters could not be updated')
        else:
            self.espeak_kw = params
            await ctx.send('Parameters successfully updated')
        finally:
            os.remove('tmp.wav')

    @commands.command(name='params')
    async def pikaparams(self, ctx, *kwargs: EspeakParamsConverter(**__espeak_valid_keys)):
        """Update pikavoice params.

        Syntax:
        !pikaparams a=amplitude
        g=gap k=emphasis p=pitch s=speed v=voice"""
        await ctx.invoke(self.params, *kwargs)

    @params.error
    @pikaparams.error
    async def pikaparams_error(self, ctx: commands.Context, exc: BaseException):
        if isinstance(exc, commands.BadArgument):
            view = ctx.view
            view.index = 0
            if view.skip_string(f'{ctx.prefix}{ctx.invoked_with}'):
                converter = EspeakParamsConverter(**self.__espeak_valid_keys)
                while not view.eof:
                    view.skip_ws()
                    arg = view.get_word()
                    try:
                        k, v = await converter.convert(ctx, arg)
                    except (KeyError, TypeError, ValueError):
                        await ctx.send(f'{ctx.author.mention}: Argument "{arg}" raised {exc.__class__.__name__}: {exc}',
                                       delete_after=10)
            else:
                self.bot.log_tb(ctx, exc)

    @say.before_invoke
    @pikasay.before_invoke
    async def voice_cmd_cancel_timeout(self, ctx: commands.Context):
        task = self.timeout_tasks.get(ctx.guild.id)
        if task is not None:
            task.cancel()


def setup(bot):
    bot.add_cog(Voice(bot))
