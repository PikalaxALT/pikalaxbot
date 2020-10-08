import discord
from discord.ext import commands, menus
import random
from . import BaseCog


_emojis = '\U0001faa8', '\U0001f4f0', '\u2702', '\u274c'


class RockPaperScissors(BaseCog):
    @commands.command(aliases=['rps'])
    @commands.max_concurrency(1)
    async def rock_paper_scissors(self, ctx: commands.Context):
        """Play a game of Rock-Paper-Scissors"""
        embed = discord.Embed(
            title=f'Rock Paper Scissors with {ctx.author}',
            description='Once all four reactions have been set, choose one to'
                        ' react with in an epic battle of Rock Paper Scissors.'
                        ' React with \u274c to cancel.',
            colour=discord.Colour.orange()
        )
        msg = await ctx.send(embed=embed)
        menu = menus.Menu(message=msg, clear_reactions_after=True)
        menu.player_move = 3
        menu.bot_move = random.randint(0, 2)

        async def reaction(menu_, payload):
            menu_.player_move = _emojis.index(str(payload.emoji))
            menu_.stop()

        for emoji in _emojis:
            menu.add_button(menus.Button(emoji, reaction))
        await menu.start(ctx, wait=True)

        if menu.player_move == 3:
            embed.description += '\n\nGame cancelled by player'
        else:
            player_emoji = _emojis[menu.player_move]
            bot_emoji = _emojis[menu.bot_move]
            diff = (menu.bot_move - menu.player_move) % 3
            # 0: tied
            # 1: bot wins
            # 2: player wins
            embed.description += f'\n\n{ctx.author}: {player_emoji}\n{self.bot.user}: {bot_emoji}\n\n'
            embed.description += ('It\'s a draw!', 'The player loses...', 'The player wins!')[diff]
        await msg.edit(embed=embed)

    async def cog_command_error(self, ctx, error):
        if isinstance(error, commands.MaxConcurrencyReached)


def setup(bot):
    bot.add_cog(RockPaperScissors(bot))
