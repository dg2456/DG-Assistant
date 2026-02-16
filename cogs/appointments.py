import discord
from discord.ext import commands
from discord import app_commands
import json
import uuid
from datetime import datetime
import config

APPOINTMENTS_FILE = "data/appointments.json"
SLOTS_FILE = "data/slots.json"


# ---------------- JSON HANDLING ---------------- #

def load_json(path):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except:
        return {}

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=4)


# ---------------- UI COMPONENTS ---------------- #

class ExtraDetailsModal(discord.ui.Modal, title="Extra Details for DG"):
    details = discord.ui.TextInput(
        label="Anything DG should know?",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=500
    )

    def __init__(self, view):
        super().__init__()
        self.view = view

    async def on_submit(self, interaction: discord.Interaction):
        self.view.extra_details = self.details.value
        await interaction.response.send_message("Extra details saved.", ephemeral=True)


class AppointmentView(discord.ui.View):
    def __init__(self, user: discord.Member, slot_id: str):
        super().__init__(timeout=300)
        self.user = user
        self.slot_id = slot_id
        self.type_selected = None
        self.extra_details = None

    @discord.ui.select(
        placeholder="Select Appointment Type",
        options=[
            discord.SelectOption(label="Commission"),
            discord.SelectOption(label="Long Term Development")
        ]
    )
    async def select_type(self, interaction: discord.Interaction, select: discord.ui.Select):
        if interaction.user != self.user:
            return await interaction.response.send_message("Not yours.", ephemeral=True)

        self.type_selected = select.values[0]
        await interaction.response.send_message(f"Selected: {self.type_selected}", ephemeral=True)

    @discord.ui.button(label="Add Extra Details", style=discord.ButtonStyle.secondary)
    async def add_details(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            return await interaction.response.send_message("Not yours.", ephemeral=True)

        await interaction.response.send_modal(ExtraDetailsModal(self))

    @discord.ui.button(label="Confirm Appointment", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            return await interaction.response.send_message("Not yours.", ephemeral=True)

        if not self.type_selected:
            return await interaction.response.send_message("Please select appointment type.", ephemeral=True)

        slots = load_json(SLOTS_FILE)
        appointments = load_json(APPOINTMENTS_FILE)

        if self.slot_id not in slots:
            return await interaction.response.send_message("This slot was already taken.", ephemeral=True)

        appointment_id = str(uuid.uuid4())[:8]

        appointment_data = {
            "user_id": self.user.id,
            "slot": slots[self.slot_id],
            "type": self.type_selected,
            "details": self.extra_details,
            "created_at": str(datetime.utcnow())
        }

        appointments[appointment_id] = appointment_data
        del slots[self.slot_id]

        save_json(APPOINTMENTS_FILE, appointments)
        save_json(SLOTS_FILE, slots)

        # Give appointment role
        role = interaction.guild.get_role(config.APPOINTMENT_ROLE_ID)
        if role:
            await self.user.add_roles(role)

        # 🔔 LOG TO CHANNEL
        log_channel = interaction.guild.get_channel(config.REMINDER_CHANNEL_ID)

        if log_channel:
            embed = discord.Embed(
                title="📅 New Appointment Booked",
                color=discord.Color.green()
            )
            embed.add_field(name="Appointment ID", value=appointment_id, inline=False)
            embed.add_field(name="User", value=self.user.mention, inline=False)
            embed.add_field(name="Slot", value=appointment_data["slot"], inline=False)
            embed.add_field(name="Type", value=self.type_selected, inline=False)

            if self.extra_details:
                embed.add_field(name="Extra Details", value=self.extra_details, inline=False)

            await log_channel.send(
                content=f"<@{config.PING_USER_ID}>",
                embed=embed
            )

        # 📩 TRY DM
        try:
            await self.user.send(
                f"✅ **Appointment Confirmed**\n\n"
                f"ID: `{appointment_id}`\n"
                f"Date: {appointment_data['slot']}\n"
                f"Type: {self.type_selected}"
            )
            dm_status = "Check your DMs."
        except:
            dm_status = "⚠️ I couldn't DM you. Please enable DMs."

        await interaction.response.send_message(
            f"Appointment confirmed! {dm_status}",
            ephemeral=True
        )

        self.stop()


# ---------------- COG ---------------- #

class Appointments(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # DG ONLY - SET APPOINTMENT SLOT
    @app_commands.command(name="appointment_set", description="Add an available appointment slot (MM/DD TIME)")
    async def appointment_set(self, interaction: discord.Interaction, date: str, time: str):
        if not any(role.id == config.STAFF_ROLE_ID for role in interaction.user.roles):
            return await interaction.response.send_message("Not authorized.", ephemeral=True)

        slots = load_json(SLOTS_FILE)

        slot_id = str(len(slots) + 1)
        slots[slot_id] = f"{date} {time}"

        save_json(SLOTS_FILE, slots)

        await interaction.response.send_message(
            f"✅ Added slot: {date} {time}",
            ephemeral=True
        )

    # USER - MAKE APPOINTMENT
    @app_commands.command(name="make_appointment")
    async def make_appointment(self, interaction: discord.Interaction):
        slots = load_json(SLOTS_FILE)

        if not slots:
            return await interaction.response.send_message(
                "No appointment slots available.",
                ephemeral=True
            )

        description = ""
        for key, value in slots.items():
            description += f"**{key}.** {value}\n"

        embed = discord.Embed(
            title="Available Appointments",
            description=description,
            color=discord.Color.blurple()
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)
        await interaction.followup.send(
            "Reply with the number of the slot you want.",
            ephemeral=True
        )

        def check(m):
            return m.author == interaction.user and m.channel == interaction.channel

        try:
            msg = await self.bot.wait_for("message", timeout=60, check=check)
            chosen = msg.content.strip()

            if chosen not in slots:
                return await interaction.followup.send("Invalid selection.", ephemeral=True)

            view = AppointmentView(interaction.user, chosen)
            await interaction.followup.send(
                "Complete your appointment below:",
                view=view,
                ephemeral=True
            )

        except:
            await interaction.followup.send("Timed out.", ephemeral=True)

    # CANCEL APPOINTMENT
    @app_commands.command(name="cancel_appointment")
    async def cancel_appointment(self, interaction: discord.Interaction, appointment_id: str):
        appointments = load_json(APPOINTMENTS_FILE)

        if appointment_id not in appointments:
            return await interaction.response.send_message("Invalid ID.", ephemeral=True)

        if appointments[appointment_id]["user_id"] != interaction.user.id:
            return await interaction.response.send_message("Not your appointment.", ephemeral=True)

        del appointments[appointment_id]
        save_json(APPOINTMENTS_FILE, appointments)

        await interaction.response.send_message("Appointment cancelled.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Appointments(bot))
