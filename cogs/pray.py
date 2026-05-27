import discord
import random
from discord.ext import commands
class Pray(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def pray(self, ctx: commands.Context = None):
        result = random.choice(["大吉","中吉"])
        print(result)
        embed = discord.Embed(title=f"{ctx.author}正在進行抽籤")
        embed.add_field(name="結果", value=result, inline=True)
        await ctx.send(embed=embed)
        


async def setup(bot: commands.Bot):
    print('>> 神社系統 <<')
    await bot.add_cog(Pray(bot))