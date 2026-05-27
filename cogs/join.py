import discord
from discord.ext import commands
class Join(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    

        #成員加入 
    @commands.Cog.listener()
    async def on_member_join(self, member):
        print(f'{member} 加入了伺服器')
        channel = self.bot.get_channel(771350927055650846)
        await channel.send(f'{member} 加入了伺服器')
    
        #成員退出
    @commands.Cog.listener()
    async def on_member_remove(self, member):
        print(f'{member} 離開了伺服器')
        channel = self.bot.get_channel(771355780695457822)
        await channel.send(f'{member} 離開了伺服器')

        

async def setup(bot: commands.Bot):
    print('>> 成員加入/退出系統 <<')
    await bot.add_cog(Join(bot))