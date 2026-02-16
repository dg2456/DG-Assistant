import discord
from discord.ext import commands
import os
import asyncio

intents = discord.Intents.all()

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash commands.")
    except Exception as e:
        print(f"Slash sync failed: {e}")

async def load_cogs():
    for file in os.listdir("./cogs"):
        if file.endswith(".py"):
            await bot.load_extension(f"cogs.{file[:-3]}")
            print(f"Loaded cog: {file}")

async def main():
    TOKEN = os.getenv("TOKEN")

    if not TOKEN:
        raise ValueError("❌ TOKEN environment variable not found.")

    async with bot:
        await load_cogs()
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
