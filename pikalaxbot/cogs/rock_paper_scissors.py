import discord
from discord.ext import commands, menus
import random
from . import BaseCog
import asyncio


_emojis = '\U0001faa8', '\U0001f4f0', '\u2702', '\u274c'


class RPSError(commands.CommandError):
    pass


class RPSMenu(menus.Menu):
    async def my_action(self, payload):
        self.player_move = _emojis.index(str(payload.emoji))
        self.stop()

    def __init__(self, player=None, opponent=None, **kwargs):
        super().__init__(**kwargs)
        self.player_move = 3
        self.player = player
        self.opponent = opponent
        self.bot_move = 3 if opponent else random.randint(0, 2)
        self.timed_out = False
        for emoji in _emojis:
            self.add_button(menus.Button(emoji, self.my_action))

    async def send_initial_message(self, ctx, channel):
        self.player = self.player or ctx.author
        self.opponent = self.opponent or ctx.me
        embed = discord.Embed(
            title=f'Rock Paper Scissors between {self.player} and {self.opponent}',
            description='Once all four reactions have been set, choose one to'
                        ' react with in an epic battle of Rock Paper Scissors.'
                        ' React with \u274c to cancel.',
            colour=discord.Colour.orange()
        )
        return await channel.send(embed=embed)

    async def finalize(self, timed_out):
        embed = self.message.embeds[0]
        if self.opponent:
            self.timed_out = timed_out
            return
        elif timed_out:
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

    def reaction_check(self, payload):
        if payload.message_id != self.message.id:
            return False
        if payload.user_id not in {self.bot.owner_id, self.player.id, *self.bot.owner_ids}:
            return False

        return payload.emoji in self.buttons


class RockPaperScissors(BaseCog):
    """Commands for playing rock-paper-scissors"""

    @commands.command(aliases=['rps'])
    @commands.max_concurrency(1, commands.BucketType.channel)
    async def rock_paper_scissors(self, ctx: commands.Context, *, opponent: discord.Member = None):
        """Play a game of Rock-Paper-Scissors with someone, or with the bot"""

        if opponent is None:
            menu = RPSMenu(clear_reactions_after=True)
            await menu.start(ctx, wait=True)
        else:
            menu1 = RPSMenu(player=ctx.author, opponent=opponent, clear_reactions_after=True)
            menu2 = RPSMenu(player=opponent, opponent=ctx.author, clear_reactions_after=True)
            msg = await ctx.send(f'Rock Paper Scissors between {ctx.author.mention} and {opponent.mention}! '
                                 f'Check your DMs!')
            tasks = [
                menu1.start(ctx, channel=ctx.author, wait=True),
                menu2.start(ctx, channel=opponent, wait=True)
            ]
            for i in range(2):
                try:
                    done, tasks = await asyncio.wait(tasks)
                    done.pop().result()
                except asyncio.TimeoutError:
                    [task.cancel() for task in tasks]
                    return await msg.edit(content='Request timed out.')
                except discord.Forbidden:
                    [task.cancel() for task in tasks]
                    return await msg.edit(content='Whoops! One or both of you has your DMs closed...')
                except Exception as e:
                    [task.cancel() for task in tasks]
                    raise RPSError from e
            if menu1.timed_out:
                return await msg.edit(content=f'{ctx.author.mention} took too long to respond...')
            elif menu1.player_move == 3:
                return await msg.edit(content=f'{ctx.author.mention} forfeited...')
            elif menu2.timed_out:
                return await msg.edit(content=f'{opponent} took too long to respond...')
            elif menu2.player_move == 3:
                return await msg.edit(content=f'{opponent} forfeited...')
            player_emoji = _emojis[menu1.player_move]
            opponent_emoji = _emojis[menu2.player_move]
            diff = menu2.player_move - menu1.player_move
            # 0: tied
            # 1: defender wins
            # 2: challenger wins
            content = msg.content
            content += f'\n\n' \
                       f'{ctx.author.mention}\'s move: {player_emoji}\n' \
                       f'{opponent.mention}\'s move: {opponent_emoji}\n\n'
            content += ['It\'s a draw!', f'{opponent.mention} wins!', f'{ctx.author.mention} wins!'][diff]
            winner = [None, opponent, ctx.author][diff]
            if winner:
                async with self.bot.sql as sql:
                    await sql.increment_score(winner, by=69)
                content += f'\n\n{winner.mention} earns 69 points for winning!'
            await msg.edit(content=content)

    async def cog_command_error(self, ctx, error):
        error = getattr(error, 'original', error)
        if isinstance(error, commands.MaxConcurrencyReached):
            await ctx.send(f'Wait your turn, {ctx.author.mention}!', delete_after=10)
        else:
            raise error


def setup(bot):
    bot.add_cog(RockPaperScissors(bot))
