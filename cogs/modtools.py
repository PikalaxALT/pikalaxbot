import asyncio
import discord
from discord.ext import commands
from utils.markov import Chain
from utils.config_io import Settings
from utils.checks import ctx_is_owner
from utils import sql


class ModTools():
    def __init__(self, bot):
        self.bot = bot

    @commands.group(pass_context=True, case_insensitive=True)
    @commands.check(ctx_is_owner)
    async def admin(self, ctx):
        """Commands for the admin console"""

    @admin.group(pass_context=True, case_insensitive=True)
    async def markov(self, ctx):
        """Commands to manage Markov channels"""

    @markov.command(name='add')
    async def add_markov(self, ctx: commands.Context, ch: discord.TextChannel):
        """Add a Markov channel by ID or mention"""
        if ch.id in self.bot.chains:
            await ctx.send(f'Channel {ch.mention} is already being tracked for Markov chains')
        else:
            async with ctx.typing():
                self.bot.chains[ch.id] = Chain(store_lowercase=True)
                try:
                    async for msg in ch.history(limit=5000):
                        self.bot.learn_markov(msg, force=True)
                    await ctx.send(f'Successfully initialized {ch.mention}')
                    with Settings() as settings:
                        settings.add_markov_channel(ch.id)
                    self.bot.markov_channels.append(ch.id)
                except discord.Forbidden:
                    self.bot.chains.pop(ch.id)
                    await ctx.send(f'Failed to get message history from {ch.mention} (403 FORBIDDEN)')
                except AttributeError:
                    self.bot.chains.pop(ch.id)
                    await ctx.send(f'Failed to load chain {ch.mention}')

    @markov.command(name='delete')
    async def del_markov(self, ctx: commands.Context, ch: discord.TextChannel):
        """Remove a Markov channel by ID or mention"""
        if ch.id in self.bot.chains:
            self.bot.chains.pop(ch.id)
            await ctx.send(f'Channel {ch.mention} has been forgotten')
            with Settings() as settings:
                settings.del_markov_channel(ch.id)
            self.bot.markov_channels.remove(ch.id)
        else:
            await ctx.send(f'Channel {ch.mention} is already forgotten')

    @admin.group(pass_context=True, case_insensitive=True)
    async def ui(self, ctx):
        """Commands to manage the bot's appearance"""

    @ui.command(name='nick')
    async def change_nick(self, ctx: commands.Context, *, nickname: str = None):
        """Change or reset the bot's nickname"""
        try:
            await ctx.me.edit(nick=nickname)
        except discord.Forbidden:
            await ctx.send('Unable to change my own nickname (FORBIDDEN)')
        else:
            await ctx.send('OwO')

    @ui.command(name='game')
    async def change_game(self, ctx: commands.Context, *, game: str = None):
        """Change or reset the bot's presence"""
        game = game or f'{ctx.prefix}pikahelp'
        activity=discord.Game(game)
        try:
            await self.bot.change_presence(activity=activity)
        except discord.Forbidden:
            await ctx.send('Unable to update my presence (FORBIDDEN)')
        else:
            with Settings() as settings:
                settings.set('user', 'game', game)

    @admin.group(pass_context=True)
    async def leaderboard(self, ctx):
        """Commands for manipulating the leaderboard"""

    @leaderboard.command(name='clear')
    async def clear_leaderboard(self, ctx):
        """Reset the leaderboard"""
        sql.reset_leaderboard()
        await ctx.send('Leaderboard reset')

    @leaderboard.command(name='give')
    async def give_points(self, ctx, person: discord.Member, score: int):
        """Give points to a player"""
        if person is None:
            await ctx.send('That person does not exist')
        else:
            sql.increment_score(person, score)
            await ctx.send(f'Gave {score:d} points to {person.name}')

    @admin.group(pass_context=True)
    async def bag(self, ctx):
        """Commands for manipulating the bag"""

    @bag.command()
    async def remove(self, ctx, msg: str):
        """Remove a phrase from the bag"""
        if sql.remove_bag(msg):
            await ctx.send('Removed message from bag')
        else:
            await ctx.send('Cannot remove default message from bag')

    @bag.command()
    async def reset(self, ctx):
        """Reset the bag"""
        sql.reset_bag()
        await ctx.send('Reset the bag')


def setup(bot):
    bot.add_cog(ModTools(bot))
