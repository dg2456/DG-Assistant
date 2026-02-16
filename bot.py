import discord
import os
import asyncio
from discord.ext import commands
from dotenv import load_dotenv
from aiohttp import web

load_dotenv()

# --- CONFIG ---
GUILD_ID = 1472669051628032002 
MY_GUILD = discord.Object(id=GUILD_ID)

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # Load Cogs
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                await self.load_extension(f'cogs.{filename[:-3]}')
        
        # Force Instant Sync to your server
        self.tree.copy_global_to(guild=MY_GUILD)
        await self.tree.sync(guild=MY_GUILD)
        print(f"✅ Synced to Guild {GUILD_ID}")

# --- RENDER PORT BINDING (Port 10000) ---
async def start_server():
    app = web.Application()
    app.router.add_get('/', lambda r: web.Response(text="Bot Active"))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 10000)
    await site.start()

async def main():
    bot = MyBot()
    async with bot:
        await asyncio.gather(start_server(), bot.start(os.getenv("DISCORD_TOKEN")))

if __name__ == "__main__":
    asyncio.run(main())
