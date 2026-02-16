import discord
import os
import asyncio
from discord.ext import commands
from dotenv import load_dotenv
from aiohttp import web

# Load .env variables for local development
load_dotenv()

# --- CONFIG ---
# Your Guild ID for instant command updates
GUILD_ID = 1472669051628032002 
MY_GUILD = discord.Object(id=GUILD_ID)

class MyBot(commands.Bot):
    def __init__(self):
        # Intents.all() is necessary for managing roles and member data
        intents = discord.Intents.all()
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        """
        Loads all Python files from the /cogs folder and syncs them to your server.
        """
        # 1. Load Cogs
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                try:
                    await self.load_extension(f'cogs.{filename[:-3]}')
                    print(f"✅ Loaded Cog: {filename}")
                except Exception as e:
                    print(f"❌ Error loading {filename}: {e}")
        
        # 2. Sync to Guild (Instant)
        # This clears old commands and ensures the new ones work immediately.
        self.tree.copy_global_to(guild=MY_GUILD)
        await self.tree.sync(guild=MY_GUILD)
        print(f"🚀 Slash commands synced to Guild: {GUILD_ID}")

    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')

# --- RENDER PORT BINDING (Fixes "Port 10000" errors) ---
async def handle(request):
    return web.Response(text="Bot is running!")

async def start_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    # Render assigns a port via the PORT env var; defaults to 10000
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"📡 Web server active on port {port}")

# --- MAIN EXECUTION ---
async def main():
    bot = MyBot()
    token = os.getenv("DISCORD_TOKEN")
    
    if not token:
        print("❌ ERROR: DISCORD_TOKEN is missing from Environment Variables!")
        return

    async with bot:
        # Runs the web server and the bot at the same time
        await asyncio.gather(
            start_server(),
            bot.start(token)
        )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
