import discord
from discord.ext import commands
from discord import app_commands
import json
import uuid
from datetime import datetime, timedelta
import os
import config
import asyncio

DATA_FILE = "data/appointments.json"


# ------------------------
# Data Handling
# ------------------------

def load_data():
    if not os.path.exists("data"):
        os.makedirs("data")

    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w") as f:
            json.dump({"slots": {}, "appointments": {}}, f)

    with open(DATA_FILE, "r") as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)


# ------------------------
# UI View
# ------------------------

class AppointmentView(discord.ui.View):
    def __init__(self, bot, user):
        super().__init__(timeout=300)
        self.bot = bot
        self.user = user
        self.selected_slot = None
        self.type = None
        self.extra = None

    @discord.ui.button(label="Select Day (Number)", style=discord.ButtonStyle.primary)
    async def select_day(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            return await interaction.response.send_message("Not yours.", ephemeral=True)

        await interaction.response.send_message("Reply with the number of the slot.", ephemeral=True)

        def check(m):
            return m.author == self.user and m.channel == interaction.channel

        try:
            msg = await self.bot.wait_for("message", timeout=120, check=check)
            data = load_data()
            slots = list(data["slots"].values())

            index = int(msg.content) - 1
            self.selected_slot = slots[index]

            await interaction.followup.send("Day selected.", ephemeral=True)
        except:
            await interaction.followup.send("Invalid selection.", ephemeral=True)

    @discord.ui.button(label="Select Type", style=discord.ButtonStyle.secondary)
    async def select_type(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            return await interaction.response.send_message("Not yours.", ephemeral=True)

        await interaction.response.send_message(
            "Reply with:\n1 = Commission\n2 = Long Term Development",
            ephemeral=True
        )

        def check(m):
            return m.author == self.user and m.channel == interaction.channel

        try:
            msg = await self.bot.wait_for("message", timeout=120, check=check)
            if msg.content == "1":
                self.type = "Commission"
            elif msg.content == "2":
                self.type = "Long Term Development"
            else:
                raise Exception

            await interaction.followup.send("Type selected.", ephemeral=True)
        except:
            await interaction.followup.send("Invalid type.", ephemeral=True)

    @discord.ui.button(label="Extra Info", style=discord.ButtonStyle.secondary)
    async def extra_info(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            return await interaction.response.send_message("Not yours.", ephemeral=True)

        await interaction.response.send_message("Reply with extra info.", ephemeral=True)

        def check(m):
            return m.author == self.user and m.channel == interaction.channel

        try:
            msg = await self.bot.wait_for("message", timeout=120, check=check)
            self.extra = msg.content
            await interaction.followup.send("Saved.", ephemeral=True)
        except:
            await interaction.followup.send("Timeout.", ephemeral=True)

    @discord.ui.button(label="Confirm Appointment", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            return await interaction.response.send_message("Not yours.", ephemeral=True)

        if not self.selected_slot or not self.type:
            return await interaction.response.send_message("Complete all fields first.", ephemeral=True)

        await interaction.response.defer()

        data = load_data()

        appointment_id = str(uuid.uuid4())[:8]

        data["appointments"][appointment_id] = {
            "user_id": self.user.id,
            "slot": self.selected_slot,
            "type": self.type,
            "extra": self.extra,
            "created": datetime.utcnow().isoformat()
        }

        save_data(data)

        guild = interaction.guild
        booked_role = guild.get_role(config.BOOKED_ROLE_ID)
        if booked_role:
            await self.user.add_roles(booked_role)

        embed = discord.Embed(
            title="Appointment Confirmed",
            description=f"""
ID: `{appointment_id}`
Time: {self.selected_slot}
Type: {self.type}
Extra: {self.extra or 'None'}
""",
            color=discord.Color.green()
        )

        try:
            await self.user.send(embed=embed)
        except:
            pass

        log_channel = guild.get_channel(config.APPOINTMENT_LOG_CHANNEL)
        if log_channel:
            await log_channel.send(
                f"<@{config.PING_USER_ID}> New Appointment",
                embed=embed
            )

        await interaction.followup.send("Appointment booked.", ephemeral=True)
        self.stop()


# ------------------------
# Cog
# ------------------------

class Appointments(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # DG ONLY
    @app_commands.command(name="appointment_set")
    async def appointment_set(self, interaction: discord.Interaction, date: str, time: str):
        if not any(role.id == config.DG_ROLE_ID for role in interaction.user.roles):
            return await interaction.response.send_message("DG only.", ephemeral=True)

        data = load_data()
        slot_id = str(uuid.uuid4())[:6]
        data["slots"][slot_id] = f"{date} {time}"
        save_data(data)

        await interaction.response.send_message(f"Slot added: {date} {time}")

    # EVERYONE
    @app_commands.command(name="make_appointment")
    async def make_appointment(self, interaction: discord.Interaction):
        data = load_data()
        slots = list(data["slots"].values())

        if not slots:
            return await interaction.response.send_message("No open slots.", ephemeral=True)

        description = "\n".join(
            f"{i+1}. {slot}" for i, slot in enumerate(slots)
        )

        embed = discord.Embed(
            title="Available Appointments",
            description=description,
            color=discord.Color.blurple()
        )

        await interaction.response.send_message(
            embed=embed,
            view=AppointmentView(self.bot, interaction.user),
            ephemeral=True
        )

    @app_commands.command(name="cancel_appointment")
    async def cancel_appointment(self, interaction: discord.Interaction, appointment_id: str):
        data = load_data()

        if appointment_id not in data["appointments"]:
            return await interaction.response.send_message("Invalid ID.", ephemeral=True)

        if data["appointments"][appointment_id]["user_id"] != interaction.user.id:
            return await interaction.response.send_message("Not yours.", ephemeral=True)

        del data["appointments"][appointment_id]
        save_data(data)

        await interaction.response.send_message("Appointment cancelled.", ephemeral=True)

    # DG CONTROL COMMANDS

    @app_commands.command(name="appointment_open")
    async def appointment_open(self, interaction: discord.Interaction, appointment_id: str):
        if not any(role.id == config.DG_ROLE_ID for role in interaction.user.roles):
            return await interaction.response.send_message("DG only.", ephemeral=True)

        data = load_data()

        if appointment_id not in data["appointments"]:
            return await interaction.response.send_message("Invalid ID.", ephemeral=True)

        user = interaction.guild.get_member(
            data["appointments"][appointment_id]["user_id"]
        )

        active_role = interaction.guild.get_role(config.ACTIVE_ROLE_ID)
        if active_role:
            await user.add_roles(active_role)

        await user.send(
            f"DG has opened your appointment `{appointment_id}`. Join in 5 minutes."
        )

        async def remove_role():
            await asyncio.sleep(300)
            if active_role in user.roles:
                await user.remove_roles(active_role)

        self.bot.loop.create_task(remove_role())

        await interaction.response.send_message("Appointment opened.")

    @app_commands.command(name="appointment_start")
    async def appointment_start(self, interaction: discord.Interaction, appointment_id: str):
        await interaction.response.send_message("Appointment started.")

    @app_commands.command(name="appointment_end")
    async def appointment_end(self, interaction: discord.Interaction, appointment_id: str):
        data = load_data()

        if appointment_id not in data["appointments"]:
            return await interaction.response.send_message("Invalid ID.", ephemeral=True)

        guild = interaction.guild
        user = guild.get_member(data["appointments"][appointment_id]["user_id"])

        active_role = guild.get_role(config.ACTIVE_ROLE_ID)
        if active_role:
            await user.remove_roles(active_role)

        archive = guild.get_channel(config.APPOINTMENT_ARCHIVE_CHANNEL)
        if archive:
            await archive.send(f"Appointment {appointment_id} completed.")

        del data["appointments"][appointment_id]
        save_data(data)

        await interaction.response.send_message("Appointment ended.")


async def setup(bot):
    await bot.add_cog(Appointments(bot))
