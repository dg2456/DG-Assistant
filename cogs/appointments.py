import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import uuid
from datetime import datetime, timedelta
import asyncio
import config

DATA_FILE = "data/appointments.json"


# -----------------------------
# DATA FUNCTIONS
# -----------------------------

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


# -----------------------------
# APPOINTMENT VIEW
# -----------------------------

class AppointmentView(discord.ui.View):
    def __init__(self, bot, user, slots):
        super().__init__(timeout=300)
        self.bot = bot
        self.user = user
        self.slots = slots
        self.selected_slot = None
        self.type = None
        self.extra = None

    async def interaction_check(self, interaction: discord.Interaction):
        return interaction.user.id == self.user.id

    @discord.ui.button(label="Select Slot (Number)", style=discord.ButtonStyle.primary)
    async def select_slot(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "Reply with the slot number.",
            ephemeral=True
        )

        def check(m):
            return m.author == self.user and m.channel == interaction.channel

        try:
            msg = await self.bot.wait_for("message", timeout=120, check=check)
            index = int(msg.content) - 1
            self.selected_slot = self.slots[index]
            await interaction.followup.send("Slot selected.", ephemeral=True)
        except:
            await interaction.followup.send("Invalid selection.", ephemeral=True)

    @discord.ui.button(label="Select Type", style=discord.ButtonStyle.secondary)
    async def select_type(self, interaction: discord.Interaction, button: discord.ui.Button):
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
        await interaction.response.send_message(
            "Reply with extra details (or type none).",
            ephemeral=True
        )

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
        if not self.selected_slot or not self.type:
            return await interaction.response.send_message(
                "Select slot and type first.",
                ephemeral=True
            )

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
            description=(
                f"**ID:** `{appointment_id}`\n"
                f"**Time:** {self.selected_slot}\n"
                f"**Type:** {self.type}\n"
                f"**Extra:** {self.extra or 'None'}"
            ),
            color=discord.Color.green()
        )

        # DM user
        try:
            await self.user.send(embed=embed)
        except:
            pass

        # Log
        log_channel = guild.get_channel(config.APPOINTMENT_LOG_CHANNEL)
        if log_channel:
            await log_channel.send(
                f"<@{config.PING_USER_ID}> New Appointment",
                embed=embed
            )

        await interaction.followup.send("Appointment booked successfully.", ephemeral=True)
        self.stop()


# -----------------------------
# COG
# -----------------------------

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

        await interaction.response.send_message(f"Slot created: {date} {time}")

    # EVERYONE
    @app_commands.command(name="make_appointment")
    async def make_appointment(self, interaction: discord.Interaction):
        data = load_data()
        slots = list(data["slots"].values())

        if not slots:
            return await interaction.response.send_message(
                "No appointment slots available.",
                ephemeral=True
            )

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
            view=AppointmentView(self.bot, interaction.user, slots),
            ephemeral=True
        )

    @app_commands.command(name="cancel_appointment")
    async def cancel_appointment(self, interaction: discord.Interaction, appointment_id: str):
        data = load_data()

        if appointment_id not in data["appointments"]:
            return await interaction.response.send_message("Invalid ID.", ephemeral=True)

        if data["appointments"][appointment_id]["user_id"] != interaction.user.id:
            return await interaction.response.send_message("Not your appointment.", ephemeral=True)

        del data["appointments"][appointment_id]
        save_data(data)

        await interaction.response.send_message("Appointment cancelled.", ephemeral=True)

    # DG COMMANDS

    @app_commands.command(name="appointment_open")
    async def appointment_open(self, interaction: discord.Interaction, appointment_id: str):
        if not any(role.id == config.DG_ROLE_ID for role in interaction.user.roles):
            return await interaction.response.send_message("DG only.", ephemeral=True)

        data = load_data()

        if appointment_id not in data["appointments"]:
            return await interaction.response.send_message("Invalid ID.", ephemeral=True)

        await interaction.response.defer()

        user = interaction.guild.get_member(
            data["appointments"][appointment_id]["user_id"]
        )

        active_role = interaction.guild.get_role(config.ACTIVE_ROLE_ID)
        if active_role:
            await user.add_roles(active_role)

        try:
            await user.send(
                f"DG has opened your appointment `{appointment_id}`. Join within 5 minutes."
            )
        except:
            pass

        await interaction.followup.send("Appointment opened.")

    @app_commands.command(name="appointment_end")
    async def appointment_end(self, interaction: discord.Interaction, appointment_id: str):
        if not any(role.id == config.DG_ROLE_ID for role in interaction.user.roles):
            return await interaction.response.send_message("DG only.", ephemeral=True)

        data = load_data()

        if appointment_id not in data["appointments"]:
            return await interaction.response.send_message("Invalid ID.", ephemeral=True)

        await interaction.response.defer()

        guild = interaction.guild
        user = guild.get_member(data["appointments"][appointment_id]["user_id"])

        active_role = guild.get_role(config.ACTIVE_ROLE_ID)
        if active_role:
            await user.remove_roles(active_role)

        archive = guild.get_channel(config.APPOINTMENT_ARCHIVE_CHANNEL)
        if archive:
            await archive.send(f"Appointment `{appointment_id}` completed.")

        del data["appointments"][appointment_id]
        save_data(data)

        await interaction.followup.send("Appointment ended.")


async def setup(bot):
    await bot.add_cog(Appointments(bot))
