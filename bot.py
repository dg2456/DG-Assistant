import discord
import os
import asyncio
from discord.ext import commands
from dotenv import load_dotenv
from aiohttp import web

load_dotenv()

# --- CONFIG ---
# Your Guild ID: 1472669051628032002
MY_GUILD = discord.Object(id=1472669051628032002)

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # 1. Load the Cogs
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                try:
                    await self.load_extension(f'cogs.{filename[:-3]}')
                    print(f"✅ Loaded Cog: {filename}")
                except Exception as e:
                    print(f"❌ Failed to load {filename}: {e}")
        
        # 2. Sync to your specific Server (Instant update)
        self.tree.copy_global_to(guild=MY_GUILD)
        await self.tree.sync(guild=MY_GUILD)
        print(f"🚀 Slash commands synced to Guild: {MY_GUILD.id}")

    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')

# --- RENDER WEB SERVER ---
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
    async with bot:
        await asyncio.gather(
            start_server(),
            bot.start(os.getenv("DISCORD_TOKEN"))
        )

if __name__ == "__main__":
    asyncio.run(main())
