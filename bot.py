import discord
import os
import asyncio
from discord.ext import commands
from dotenv import load_dotenv

# Load .env only if running locally. 
# On Render, it uses the Dashboard variables automatically.
load_dotenv()

class MyBot(commands.Bot):
    def __init__(self):
        # Intents allow the bot to see members, messages, and roles
        intents = discord.Intents.all()
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # This looks into your /cogs folder and loads appointment.py and work.py
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                try:
                    await self.load_extension(f'cogs.{filename[:-3]}')
                    print(f"Loaded extension: {filename}")
                except Exception as e:
                    print(f"Failed to load extension {filename}: {e}")
        
        # Syncs your /commands so they show up in Discord
        await self.tree.sync()
        print("Slash commands synced.")

    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        print("------")

# Create the bot instance
bot = MyBot()

# Grab the token from the Environment Variable
TOKEN = os.getenv("DISCORD_TOKEN")

if __name__ == "__main__":
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("ERROR: No DISCORD_TOKEN found! Did you add it to Render's Environment Variables?")
