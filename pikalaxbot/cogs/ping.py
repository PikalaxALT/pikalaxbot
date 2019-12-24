from discord.ext import commands
from . import BaseCog


class Ping(BaseCog):
    @commands.command()
    async def ping(self, ctx: commands.Context):
        new = await ctx.send('Pong!')
        delta = new.created_at - ctx.message.created_at
        await new.edit(content=f'Pong!\n'
                               f'Round trip: {delta.total_seconds() * 1000:.0f} ms\n'
                               f'Heartbeat latency: {self.bot.latency * 1000:.0f} ms')


def setup(bot):
    bot.add_cog(Ping(bot))
