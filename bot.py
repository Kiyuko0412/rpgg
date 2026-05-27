import os
import asyncio
import discord
from discord.ext import commands
import json
import traceback

# 基本設定含token
with open("setting.json", 'r', encoding='utf8') as f:
    conf = json.load(f)

class JuBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix="=", intents=intents)
        # 掃描 cogs 
        self.init_cogs = [f'cogs.{n[:-3]}' for n in os.listdir("./cogs") if n.endswith(".py")]

    async def setup_hook(self):
        """初始化"""
        for ext in self.init_cogs:
            try:
                await self.load_extension(ext)
            except Exception as e:
                print(f'載入 {ext} 失敗：{e}')

        print("同步斜線指令...")
        try:
            # 清理一下舊的指令並同步
            synced = await self.tree.sync()
            print(f"成功同步 {len(synced)} 個指令")
        except Exception as e:
            print(f"同步指令出錯：{e}")

    async def on_ready(self):
        """上線啦"""
        print(f">> 登入成功：{self.user} (ID: {self.user.id}) <<")
        await self.notify_online()
        self.loop.create_task(self.ping_loop())

    async def notify_online(self):
        """開機通知"""
        ch = self.get_channel(conf['NOTIFY_CHANNEL_ID'])
        if ch:
            await ch.send("> :baby_chick: 鳩鳩破殼而出啦！")
            emb = discord.Embed(title="鳩鳩已就位！", color=0x1f4239)
            emb.set_author(name="運行通知", icon_url="https://imgur.com/dyK7Qz8.jpg")
            await ch.send(embed=emb)

    async def ping_loop(self):
        """每分鐘更新一次延遲"""
        ch = self.get_channel(conf['PING_CHANNEL_ID'])
        if not ch: return
        msg = await ch.fetch_message(conf['PING_MESSAGE_ID'])
        
        while not self.is_closed():
            lat = round(self.latency * 1000)
            await msg.edit(content=f":hatching_chick: 鳩鳩目前延遲：{lat}ms :hatching_chick:")
            await asyncio.sleep(60)

bot = JuBot()

@bot.command()
@commands.is_owner()
async def load(ctx, ext):
    """載入"""
    await bot.load_extension(f"cogs.{ext}")
    await ctx.send(f"已載入 {ext}")

@bot.command()
@commands.is_owner()
async def unload(ctx, ext):
    """移除"""
    await bot.unload_extension(f"cogs.{ext}")
    await ctx.send(f"已移除 {ext}")

@bot.command()
@commands.is_owner()
async def reload(ctx, ext):
    """重載"""
    await bot.reload_extension(f"cogs.{ext}")
    await ctx.send(f"已重載{ext}")

@bot.command()
@commands.is_owner()
async def sync(ctx):
    """手動同步指令"""
    await bot.tree.sync()
    await ctx.send("指令同步完成！")

async def main():
    async with bot:
        await bot.start(conf['token'])

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("機器人已關閉。")
