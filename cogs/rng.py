import asyncio
import discord
import random
from discord.ext import commands
from cogs import Cog


class DiceRollConverter(commands.Converter):
    async def convert(self, ctx, argument):
        argument = argument.lower()
        count, sides = argument.split('d')
        if not (count or sides):
            raise commands.BadArgument(f'When supplying an argument to {ctx.prefix}{ctx.command}, '
                                       f'at least one of count or sides must be provided.')
        count = int(count) if count else 1
        sides = int(sides) if sides else 6
        assert count in range(1, 200) and sides in range(2, 100)
        return count, sides


class Rng(Cog):
    @commands.command()
    async def choose(self, ctx: commands.Context, *args):
        await ctx.send(random.choice(args))

    @commands.command()
    async def roll(self, ctx, *, params=(1, 6)):
        count, sides = params
        rolls = [random.randint(1, sides) for i in range(count)]
        rollstr = ', '.join(rolls)
        dice = 'die' if count == 1 else 'dice'
        await ctx.send(f'Rolled {count} {sides}-sided {dice}.  Result:\n'
                       f'{rollstr}')

    async def __error(self, ctx, exc):
        await ctx.send(f'**{exc.__class__.__name__}:** {exc}')
        self.log_tb(ctx, exc)


def setup(bot):
    bot.add_cog(Rng(bot))
