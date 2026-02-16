import discord
from discord.ext import commands
from discord import app_commands
import json
import config

def load_data():
    with open("data/appointments.json", "r") as f:
        return json.load(f)

def save_data(data):
    with open("data/appointments.json", "w") as f:
        json.dump(data, f, indent=4)

class AppointmentStaff(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def staff_only():
        async def predicate(interaction: discord.Interaction):
            return any(role.id == config.STAFF_ROLE_ID for role in interaction.user.roles)
        return app_commands.check(predicate)

    @app_commands.command(name="appointment_open")
    @staff_only()
    async def open(self, interaction: discord.Interaction, appointment_id: str):
        data = load_data()
        if appointment_id not in data:
            return await interaction.response.send_message("Invalid ID", ephemeral=True)

        user = interaction.guild.get_member(data[appointment_id]["user_id"])

        await user.send(
            f"DG has opened your appointment `{appointment_id}`.\n"
            "Join his office in 5 minutes or it will be removed."
        )

        role = interaction.guild.get_role(config.ACTIVE_APPOINTMENT_ROLE_ID)
        await user.add_roles(role)

        await interaction.response.send_message("Opened appointment.", ephemeral=True)

    @app_commands.command(name="appointment_start")
    @staff_only()
    async def start(self, interaction: discord.Interaction, appointment_id: str):
        await interaction.response.send_message("Appointment started.", ephemeral=True)

    @app_commands.command(name="appointment_end")
    @staff_only()
    async def end(self, interaction: discord.Interaction, appointment_id: str):
        data = load_data()
        if appointment_id not in data:
            return await interaction.response.send_message("Invalid ID", ephemeral=True)

        user = interaction.guild.get_member(data[appointment_id]["user_id"])
        role = interaction.guild.get_role(config.ACTIVE_APPOINTMENT_ROLE_ID)
        await user.remove_roles(role)

        del data[appointment_id]
        save_data(data)

        await interaction.response.send_message("Appointment ended.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(AppointmentStaff(bot))
