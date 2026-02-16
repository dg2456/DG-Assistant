import discord
from discord.ext import commands
from discord import app_commands
import json
import uuid
import config

def load_data():
    try:
        with open("data/work.json", "r") as f:
            return json.load(f)
    except:
        return {}

def save_data(data):
    with open("data/work.json", "w") as f:
        json.dump(data, f, indent=4)

class Work(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="work_add")
    async def add(self, interaction: discord.Interaction, user: discord.Member, due_date: str = None, info: str = None, robux: int = None):
        work_id = str(uuid.uuid4())[:8]
        data = load_data()

        data[work_id] = {
            "user": user.id,
            "due": due_date,
            "info": info,
            "robux": robux
        }

        save_data(data)

        channel = self.bot.get_channel(config.WORK_LOG_CHANNEL_ID)
        await channel.send(f"New Work ID `{work_id}` for {user.mention}")

        await interaction.response.send_message("Work added.", ephemeral=True)

    @app_commands.command(name="work_complete")
    async def complete(self, interaction: discord.Interaction, work_id: str):
        data = load_data()
        if work_id not in data:
            return await interaction.response.send_message("Invalid ID", ephemeral=True)

        channel = self.bot.get_channel(config.WORK_COMPLETE_CHANNEL_ID)
        await channel.send(f"Completed Work `{work_id}`")

        del data[work_id]
        save_data(data)

        await interaction.response.send_message("Work completed.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Work(bot))
