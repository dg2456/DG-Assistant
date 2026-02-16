import discord
import os
import asyncio
from discord.ext import commands
from dotenv import load_dotenv
from aiohttp import web

load_dotenv()

# --- CONFIG ---
# Enter your Guild ID here one last time to CLEAR the duplicates
MY_GUILD_ID = 1472669051628032002 

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # 1. Load Cogs
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                try:
                    await self.load_extension(f'cogs.{filename[:-3]}')
                    print(f"✅ Loaded: {filename}")
                except Exception as e:
                    print(f"❌ Error {filename}: {e}")
        
        # 2. CLEAR DUPLICATES
        # This removes the commands from your specific server so only Global remains
        guild = discord.Object(id=MY_GUILD_ID)
        self.tree.clear_commands(guild=guild)
        await self.tree.sync(guild=guild)
        print(f"🗑️ Cleared duplicate commands from Guild {MY_GUILD_ID}")

        # 3. SYNC GLOBAL
        await self.tree.sync()
        print("🚀 Global Slash commands synced.")

    async def on_ready(self):
        print(f'Logged in as {self.user}')

# --- RENDER PORT BINDING ---
async def handle(request):
    return web.Response(text="Bot is running!")

async def start_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

async def main():
    bot = MyBot()
    token = os.getenv("DISCORD_TOKEN")
    async with bot:
        await asyncio.gather(start_server(), bot.start(token))

if __name__ == "__main__":
    asyncio.run(main())
