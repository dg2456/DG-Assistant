import discord
import os
import asyncio
from discord.ext import commands
from dotenv import load_dotenv
from aiohttp import web

load_dotenv()

# --- CONFIG ---
# We are removing the GUILD_ID restriction to make commands GLOBAL
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
                    print(f"✅ Loaded Cog: {filename}")
                except Exception as e:
                    print(f"❌ Error loading {filename}: {e}")
        
        # 2. Register GLOBAL Commands
        # This replaces the Guild sync. It may take up to 1 hour to appear everywhere.
        await self.tree.sync() 
        print("🚀 Global Slash commands synced to Discord API.")

    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')

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
    
    if not token:
        print("❌ ERROR: DISCORD_TOKEN is missing!")
        return

    async with bot:
        await asyncio.gather(
            start_server(),
            bot.start(token)
        )

if __name__ == "__main__":
    asyncio.run(main())
