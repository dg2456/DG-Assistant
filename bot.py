import discord
import os
import asyncio
from discord.ext import commands
from dotenv import load_dotenv
from aiohttp import web

# Load .env variables for local development
load_dotenv()

# --- CONFIG ---
# Your Guild ID: 1472669051628032002
MY_GUILD = discord.Object(id=1472669051628032002)

class MyBot(commands.Bot):
    def __init__(self):
        # Intents.all() is required to manage roles and members across cogs
        intents = discord.Intents.all()
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        """
        Executed when the bot starts. This loads Cogs and syncs slash commands.
        """
        # 1. Load extensions from the /cogs folder
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                try:
                    await self.load_extension(f'cogs.{filename[:-3]}')
                    print(f"✅ Successfully loaded Cog: {filename}")
                except Exception as e:
                    print(f"❌ Failed to load Cog {filename}: {e}")
        
        # 2. Sync commands specifically to your Guild for instant updates
        # This prevents the "Application not responding" due to outdated command trees
        self.tree.copy_global_to(guild=MY_GUILD)
        await self.tree.sync(guild=MY_GUILD)
        print(f"🚀 Slash commands synced to Guild ID: {MY_GUILD.id}")

    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        print("Bot is fully operational and listening for commands.")

# --- RENDER WEB SERVER (PORT 10000) ---
async def handle(request):
    """Simple health check for Render's port binding."""
    return web.Response(text="Bot is online and responsive.")

async def start_server():
    """Starts the aiohttp server on port 10000."""
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Render provides a PORT env var, defaults to 10000
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"📡 Web server listening on port {port}")

# --- MAIN RUNNER ---
async def main():
    bot = MyBot()
    token = os.getenv("DISCORD_TOKEN")
    
    if not token:
        print("❌ CRITICAL ERROR: DISCORD_TOKEN not found in environment variables.")
        return

    # Run the web server and the bot simultaneously
    async with bot:
        await asyncio.gather(
            start_server(),
            bot.start(token)
        )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot shutting down...")
