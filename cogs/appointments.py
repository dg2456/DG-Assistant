import discord
from discord.ext import commands
from discord import app_commands
import json
import uuid
from datetime import datetime
import config

def load_data():
    try:
        with open("data/appointments.json", "r") as f:
            return json.load(f)
    except:
        return {}

def save_data(data):
    with open("data/appointments.json", "w") as f:
        json.dump(data, f, indent=4)

class Appointments(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="make_appointment")
    async def make_appointment(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            "Reply with:\n"
            "1️⃣ Day (number)\n"
            "2️⃣ Type (Commission / Long Term Development)\n"
            "3️⃣ Extra info\n\n"
            "Send in this format:\n"
            "`Day | Type | Info`",
            ephemeral=True
        )

        def check(m):
            return m.author == interaction.user and m.channel == interaction.channel

        try:
            msg = await self.bot.wait_for("message", timeout=120, check=check)
            day, type_, info = msg.content.split("|")

            appointment_id = str(uuid.uuid4())[:8]
            data = load_data()

            data[appointment_id] = {
                "user_id": interaction.user.id,
                "day": day.strip(),
                "type": type_.strip(),
                "info": info.strip(),
                "timestamp": str(datetime.utcnow())
            }

            save_data(data)

            role = interaction.guild.get_role(config.APPOINTMENT_ROLE_ID)
            await interaction.user.add_roles(role)

            embed = discord.Embed(
                title="Appointment Confirmed",
                description=f"ID: `{appointment_id}`\nDay: {day}\nType: {type_}\nInfo: {info}",
                color=discord.Color.green()
            )

            await interaction.user.send(embed=embed)

            await interaction.followup.send("Appointment created!", ephemeral=True)

        except:
            await interaction.followup.send("Invalid format or timeout.", ephemeral=True)

    @app_commands.command(name="cancel_appointment")
    async def cancel_appointment(self, interaction: discord.Interaction, appointment_id: str):
        data = load_data()

        if appointment_id not in data:
            return await interaction.response.send_message("Invalid ID.", ephemeral=True)

        if data[appointment_id]["user_id"] != interaction.user.id:
            return await interaction.response.send_message("Not your appointment.", ephemeral=True)

        del data[appointment_id]
        save_data(data)

        await interaction.response.send_message("Appointment cancelled.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Appointments(bot))
