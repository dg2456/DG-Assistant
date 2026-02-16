import discord
import os
import asyncio
from discord.ext import commands
from dotenv import load_dotenv
from aiohttp import web

load_dotenv()

# --- CONFIG ---
# Put your Server ID here for instant command syncing
GUILD_ID = 1472669051628032002  # <--- REPLACE THIS WITH YOUR SERVER ID

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # Load Cogs
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                await self.load_extension(f'cogs.{filename[:-3]}')
                print(f"✅ Loaded Cog: {filename}")
        
        # Syncing Logic
        guild = discord.Object(id=GUILD_ID)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)
        print(f"✅ Synced commands to guild: {GUILD_ID}")

    async def on_ready(self):
        print(f'Logged in as {self.user}')

# --- RENDER PORT BINDING ---
async def handle(request):
    return web.Response(text="Bot is alive!")

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
        await asyncio.gather(start_server(), bot.start(os.getenv("DISCORD_TOKEN")))

if __name__ == "__main__":
    asyncio.run(main())
