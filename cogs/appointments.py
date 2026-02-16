import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import uuid
from datetime import datetime, timedelta
import config

APPOINTMENTS_FILE = "data/appointments.json"
SLOTS_FILE = "data/slots.json"

ACTIVE_ROLE_ID = 1472691907959460077
STAFF_ROLE_ID = config.STAFF_ROLE_ID
STAFF_PING_ROLE_ID = 1472681773577142459
TODAY_CHANNEL_ID = 1472691188233539645
COMPLETED_CHANNEL_ID = 1472765152138100787


# ---------------- JSON ---------------- #

def load_json(path):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except:
        return {}

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=4)


# ---------------- COG ---------------- #

class Appointments(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.auto_cancel_loop.start()
        self.daily_reminder_loop.start()

    # ---------------- AUTO CANCEL ---------------- #

    @tasks.loop(seconds=60)
    async def auto_cancel_loop(self):
        appointments = load_json(APPOINTMENTS_FILE)
        now = datetime.utcnow()

        changed = False

        for aid, data in list(appointments.items()):
            if data.get("status") == "open":
                opened_at = datetime.fromisoformat(data["opened_at"])
                if now - opened_at > timedelta(minutes=5):
                    # Cancel
                    guild = self.bot.get_guild(data["guild_id"])
                    if guild:
                        member = guild.get_member(data["user_id"])
                        role = guild.get_role(ACTIVE_ROLE_ID)
                        if member and role:
                            try:
                                await member.remove_roles(role)
                            except:
                                pass

                    del appointments[aid]
                    changed = True

        if changed:
            save_json(APPOINTMENTS_FILE, appointments)

    # ---------------- DAILY REMINDER ---------------- #

    @tasks.loop(minutes=5)
    async def daily_reminder_loop(self):
        appointments = load_json(APPOINTMENTS_FILE)
        today = datetime.utcnow().strftime("%m/%d")

        for aid, data in appointments.items():
            if today in data.get("slot", "") and not data.get("reminded"):
                guild = self.bot.get_guild(data["guild_id"])
                if not guild:
                    continue

                channel = guild.get_channel(TODAY_CHANNEL_ID)
                if not channel:
                    continue

                try:
                    message = await channel.fetch_message(data["message_id"])
                except:
                    continue

                await message.reply(
                    f"<@&{STAFF_PING_ROLE_ID}> 📅 **This appointment is TODAY**"
                )

                data["reminded"] = True
                save_json(APPOINTMENTS_FILE, appointments)

    # ---------------- OPEN ---------------- #

    @app_commands.command(name="appointment_open")
    async def appointment_open(self, interaction: discord.Interaction, appointment_id: str):

        await interaction.response.defer(ephemeral=True)

        if not any(role.id == STAFF_ROLE_ID for role in interaction.user.roles):
            return await interaction.followup.send("Not authorized.", ephemeral=True)

        appointments = load_json(APPOINTMENTS_FILE)

        if appointment_id not in appointments:
            return await interaction.followup.send("Invalid appointment ID.", ephemeral=True)

        data = appointments[appointment_id]
        guild = interaction.guild
        member = guild.get_member(data["user_id"])

        role = guild.get_role(ACTIVE_ROLE_ID)
        if member and role:
            await member.add_roles(role)

        data["status"] = "open"
        data["opened_at"] = datetime.utcnow().isoformat()
        data["guild_id"] = guild.id

        save_json(APPOINTMENTS_FILE, appointments)

        try:
            await member.send(f"Your appointment `{appointment_id}` is now OPEN.")
        except:
            pass

        await interaction.followup.send("Appointment opened.", ephemeral=True)

    # ---------------- START ---------------- #

    @app_commands.command(name="appointment_start")
    async def appointment_start(self, interaction: discord.Interaction, appointment_id: str):

        await interaction.response.defer(ephemeral=True)

        appointments = load_json(APPOINTMENTS_FILE)

        if appointment_id not in appointments:
            return await interaction.followup.send("Invalid appointment ID.", ephemeral=True)

        appointments[appointment_id]["status"] = "started"
        save_json(APPOINTMENTS_FILE, appointments)

        await interaction.followup.send("Appointment started.", ephemeral=True)

    # ---------------- END ---------------- #

    @app_commands.command(name="appointment_end")
    async def appointment_end(self, interaction: discord.Interaction, appointment_id: str):

        await interaction.response.defer(ephemeral=True)

        appointments = load_json(APPOINTMENTS_FILE)

        if appointment_id not in appointments:
            return await interaction.followup.send("Invalid appointment ID.", ephemeral=True)

        data = appointments[appointment_id]
        guild = interaction.guild
        member = guild.get_member(data["user_id"])

        role = guild.get_role(ACTIVE_ROLE_ID)
        if member and role:
            await member.remove_roles(role)

        completed_channel = guild.get_channel(COMPLETED_CHANNEL_ID)

        if completed_channel:
            embed = discord.Embed(title="✅ Appointment Completed", color=discord.Color.green())
            embed.add_field(name="ID", value=appointment_id)
            embed.add_field(name="User", value=member.mention if member else "Unknown")
            embed.add_field(name="Slot", value=data["slot"])
            embed.add_field(name="Type", value=data["type"])
            await completed_channel.send(embed=embed)

        del appointments[appointment_id]
        save_json(APPOINTMENTS_FILE, appointments)

        await interaction.followup.send("Appointment ended.", ephemeral=True)

    # ---------------- PREVENT DOUBLE BOOKING ---------------- #

    @app_commands.command(name="make_appointment")
    async def make_appointment(self, interaction: discord.Interaction, slot: str, type: str):

        await interaction.response.defer(ephemeral=True)

        appointments = load_json(APPOINTMENTS_FILE)

        for data in appointments.values():
            if data["user_id"] == interaction.user.id:
                return await interaction.followup.send(
                    "You already have an appointment booked.",
                    ephemeral=True
                )

        appointment_id = str(uuid.uuid4())[:8]

        embed = discord.Embed(title="📅 New Appointment", color=discord.Color.green())
        embed.add_field(name="ID", value=appointment_id)
        embed.add_field(name="User", value=interaction.user.mention)
        embed.add_field(name="Slot", value=slot)
        embed.add_field(name="Type", value=type)

        channel = interaction.guild.get_channel(TODAY_CHANNEL_ID)
        message = await channel.send(
            f"<@&{STAFF_PING_ROLE_ID}>",
            embed=embed
        )

        appointments[appointment_id] = {
            "user_id": interaction.user.id,
            "slot": slot,
            "type": type,
            "status": "booked",
            "guild_id": interaction.guild.id,
            "message_id": message.id,
            "reminded": False
        }

        save_json(APPOINTMENTS_FILE, appointments)

        await interaction.followup.send("Appointment booked.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Appointments(bot))
