import discord
from discord.ext import commands, menus
import random
from . import BaseCog


_emojis = '\U0001faa8', '\U0001f4f0', '\u2702', '\u274c'


class RPSMenu(menus.Menu):
    async def my_action(self, payload):
        self.player_move = _emojis.index(str(payload.emoji))
        self.stop()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.player_move = 3
        self.bot_move = random.randint(0, 2)
        for emoji in _emojis:
            self.add_button(menus.Button(emoji, self.my_action))

    async def send_initial_message(self, ctx, channel):
        embed = discord.Embed(
            title=f'Rock Paper Scissors with {ctx.author}',
            description='Once all four reactions have been set, choose one to'
                        ' react with in an epic battle of Rock Paper Scissors.'
                        ' React with \u274c to cancel.',
            colour=discord.Colour.orange()
        )
        return await channel.send(embed=embed)

    async def finalize(self, timed_out):
        embed = self.message.embeds[0]
        if timed_out:
            embed.description += '\n\nTime\'s up, the player left'
        elif self.player_move == 3:
            embed.description += '\n\nGame cancelled by player'
        else:
            player_emoji = _emojis[self.player_move]
            bot_emoji = _emojis[self.bot_move]
            diff = self.bot_move - self.player_move
            # 0: tied
            # 1: bot wins
            # 2: player wins
            embed.description += f'\n\n{self.ctx.author}: {player_emoji}\n{self.bot.user}: {bot_emoji}\n\n'
            embed.description += ('It\'s a draw!', 'The player loses...', 'The player wins!')[diff]
            embed.colour = (discord.Colour.dark_gray, discord.Colour.red, discord.Colour.green)[diff]()
        await self.message.edit(embed=embed)


class RockPaperScissors(BaseCog):
    """Commands for playing rock-paper-scissors"""

    @commands.command(aliases=['rps'])
    @commands.max_concurrency(1, commands.BucketType.channel)
    async def rock_paper_scissors(self, ctx: commands.Context):
        """Play a game of Rock-Paper-Scissors"""
        menu = RPSMenu(clear_reactions_after=True)
        await menu.start(ctx, wait=True)

    async def cog_command_error(self, ctx, error):
        error = getattr(error, 'original', error)
        if isinstance(error, commands.MaxConcurrencyReached):
            await ctx.send(f'Wait your turn, {ctx.author.mention}!', delete_after=10)
        else:
            raise error


def setup(bot):
    bot.add_cog(RockPaperScissors(bot))
