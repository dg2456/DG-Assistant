import discord
from discord.ext import commands
from discord import app_commands
import os
import asyncio
from flask import Flask
from threading import Thread

# ---------------- CONFIG ---------------- #
TOKEN = os.environ.get("TOKEN")  # Set this in Render environment variables
PORT = 10000

# ---------------- INTENTS ---------------- #
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ---------------- FLASK KEEP-ALIVE ---------------- #
app = Flask("")

@app.route("/")
def home():
    return "Bot is running!"

def run_flask():
    app.run(host="0.0.0.0", port=PORT)

Thread(target=run_flask).start()

# ---------------- BOT EVENTS ---------------- #
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    try:
        # Sync globally (or use guild for faster testing)
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands.")
    except Exception as e:
        print("Command sync failed:", e)

# ---------------- COG LOADER ---------------- #
async def load_cogs():
    for file in os.listdir("./cogs"):
        if file.endswith(".py"):
            try:
                await bot.load_extension(f"cogs.{file[:-3]}")
                print(f"Loaded cog: {file}")
            except Exception as e:
                print(f"Failed to load cog {file}: {e}")

asyncio.run(load_cogs())

# ---------------- RUN BOT ---------------- #
if not TOKEN:
    print("Error: TOKEN environment variable not set!")
else:
    bot.run(TOKEN)
