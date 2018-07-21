import asyncio
import discord
from discord.ext import commands
from concurrent.futures._base import Error
from collections import OrderedDict, deque

player_rxns = OrderedDict()


class VoiceCommandError(commands.CommandError):
    """This is raised when an error occurs in a voice command."""


def player_reaction(emoji):
    def decorator(coro):
        player_rxns[emoji] = coro
        return coro

    return decorator


@player_reaction('⏭')
async def yt_skip_video(self, ctx):
    ctx.guild.voice_client.stop()


@player_reaction('⏹')
async def yt_cancel_playlist(self, ctx):
    await self.destroy_ytplayer_message(ctx)
    ctx.guild.voice_client.stop()


@player_reaction('⏸')
@player_reaction('▶')
async def yt_pause_playlist(self, ctx: commands.Context):
    if ctx.guild.voice_client.is_paused():
        ctx.guild.voice_client.resume()
    else:
        ctx.guild.voice_client.pause()


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)

        self.data = data

        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    def from_info(cls, filename, video, **kwargs):
        return cls(discord.FFmpegPCMAudio(filename, **kwargs), data=video)


class YouTubePlaylistHandler:
    def __init__(self, *, loop=None):
        self.loop = loop or asyncio.get_event_loop()
        self.message: discord.Message = None
        self.task: asyncio.Task = None
        self.playlist = deque()
    
    def __bool__(self):
        return len(self.playlist) > 0
    
    def __len__(self):
        return len(self.playlist)
    
    def popleft(self):
        return self.playlist.popleft()
    
    def extend(self, iterable):
        self.playlist.extend(iterable)
    
    async def controls_task(self, ctx: commands.Context):
        def predicate(rxn, usr):
            return rxn.message.id == self.message.id and rxn.emoji in player_rxns

        while True:
            tasks = [ctx.bot.wait_for(event, check=predicate) for event in ('reaction_add', 'reaction_remove')]
            done, left = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            try:
                reaction, user = done.pop().result()
            except IndexError:
                break
            except Error as e:
                raise VoiceCommandError from e
            for task in left:
                task.cancel()
            await player_rxns[reaction.emoji](self, ctx)

    async def set_message(self, ctx, **fields):
        if self.message:
            await self.message.edit(**fields)
        else:
            self.message = await ctx.send(**fields)
            for emoji in player_rxns:
                await self.message.add_reaction(emoji)
            if not self.task:
                self.task = self.loop.create_task(self.controls_task(ctx))

    async def destroy_task(self):
        if not self.task.cancelled():
            self.task.cancel()
        self.playlist.clear()
        try:
            await self.message.delete()
        except discord.HTTPException:
            pass
