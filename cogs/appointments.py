import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import uuid
from datetime import datetime, timedelta
import config
import asyncio
import os

DATA_FILE = "data/appointments.json"

def load_data():
    if not os.path.exists("data"):
        os.makedirs("data")
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w") as f:
            json.dump({}, f)
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

class AppointmentView(discord.ui.View):
    def __init__(self, bot, user, slot):
        super().__init__(timeout=300)
        self.bot = bot
        self.user = user
        self.slot = slot
        self.type = None
        self.extra_info = None

    @discord.ui.select(
        placeholder="Select Appointment Type",
        options=[
            discord.SelectOption(label="Long Term Development"),
            discord.SelectOption(label="Commission"),
        ]
    )
    async def select_type(self, interaction: discord.Interaction, select: discord.ui.Select):
        if interaction.user != self.user:
            return await interaction.response.send_message("Not your appointment.", ephemeral=True)

        self.type = select.values[0]
        await interaction.response.send_message("Type selected. Now click 'Add Extra Info'.", ephemeral=True)

    @discord.ui.button(label="Add Extra Info", style=discord.ButtonStyle.secondary)
    async def extra_info_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            return await interaction.response.send_message("Not yours.", ephemeral=True)

        await interaction.response.send_message("Reply with extra details for DG.", ephemeral=True)

        def check(m):
            return m.author == self.user and m.channel == interaction.channel

        try:
            msg = await self.bot.wait_for("message", timeout=120, check=check)
            self.extra_info = msg.content
            await interaction.followup.send("Extra info saved. Now click Confirm.", ephemeral=True)
        except:
            await interaction.followup.send("Timed out.", ephemeral=True)

    @discord.ui.button(label="Confirm Appointment", style=discord.ButtonStyle.success)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            return await interaction.response.send_message("Not yours.", ephemeral=True)

        if not self.type:
            return await interaction.response.send_message("Select type first.", ephemeral=True)

        await interaction.response.defer()

        data = load_data()

        for a in data.values():
            if a["slot"] == self.slot:
                return await interaction.followup.send("Slot already taken.", ephemeral=True)

        appointment_id = str(uuid.uuid4())[:8]

        data[appointment_id] = {
            "user_id": self.user.id,
            "slot": self.slot,
            "type": self.type,
            "extra_info": self.extra_info,
            "message_id": interaction.message.id
        }

        save_data(data)

        role = interaction.guild.get_role(config.PING_ROLE_ID)
        ping = role.mention if role else ""

        embed = discord.Embed(
            title="📅 New Appointment Booked",
            description=f"**ID:** `{appointment_id}`\n"
                        f"**User:** {self.user.mention}\n"
                        f"**Time:** {self.slot}\n"
                        f"**Type:** {self.type}\n"
                        f"**Extra Info:** {self.extra_info or 'None'}",
            color=discord.Color.green()
        )

        log_channel = interaction.guild.get_channel(config.LOG_CHANNEL_ID)
        if log_channel:
            await log_channel.send(content=ping, embed=embed)

        try:
            await self.user.send(embed=embed)
        except:
            pass

        await interaction.followup.send("✅ Appointment Confirmed!", ephemeral=True)
        self.stop()

class Appointments(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.reminder_loop.start()

    def cog_unload(self):
        self.reminder_loop.cancel()

    @app_commands.command(name="appointment_set")
    async def appointment_set(self, interaction: discord.Interaction, date: str, time: str):
        if not any(role.id == config.DG_ROLE_ID for role in interaction.user.roles):
            return await interaction.response.send_message("DG only.", ephemeral=True)

        slot = f"{date} {time}"
        data = load_data()

        data[str(uuid.uuid4())[:6]] = {
            "slot": slot,
            "open": True
        }

        save_data(data)

        await interaction.response.send_message(f"✅ Appointment slot set for {slot}")

    @app_commands.command(name="make_appointment")
    async def make_appointment(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        data = load_data()
        slots = [v["slot"] for v in data.values() if v.get("open")]

        if not slots:
            return await interaction.followup.send("No open appointments.")

        description = "\n".join(f"{i+1}. {slot}" for i, slot in enumerate(slots))

        embed = discord.Embed(
            title="Available Appointments",
            description=description,
            color=discord.Color.blurple()
        )

        view = AppointmentView(self.bot, interaction.user, slots[0])
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="appointment_open")
    async def appointment_open(self, interaction: discord.Interaction):
        await interaction.response.send_message("Appointments are open.")

    @app_commands.command(name="appointment_end")
    async def appointment_end(self, interaction: discord.Interaction):
        await interaction.response.defer()

        data = load_data()
        today = datetime.now().strftime("%m/%d")

        removed = []

        for key in list(data.keys()):
            if today in data[key].get("slot", ""):
                removed.append(data[key])
                del data[key]

        save_data(data)

        log_channel = interaction.guild.get_channel(1472765152138100787)

        for appt in removed:
            embed = discord.Embed(
                title="📁 Appointment Completed",
                description=f"User: <@{appt['user_id']}>\nTime: {appt['slot']}",
                color=discord.Color.red()
            )
            if log_channel:
                await log_channel.send(embed=embed)

        await interaction.followup.send("Today's appointments ended.")

    @tasks.loop(minutes=1)
    async def reminder_loop(self):
        await self.bot.wait_until_ready()
        data = load_data()
        now = datetime.now()

        for appt_id, appt in data.items():
            if "slot" not in appt:
                continue

            try:
                appt_time = datetime.strptime(appt["slot"], "%m/%d %H:%M")
                appt_time = appt_time.replace(year=now.year)

                guild = self.bot.guilds[0]
                role = guild.get_role(config.PING_ROLE_ID)

                if appt_time.strftime("%m/%d") == now.strftime("%m/%d"):
                    channel = guild.get_channel(config.LOG_CHANNEL_ID)
                    if channel:
                        await channel.send(
                            f"{role.mention} 📅 Appointment is today for <@{appt['user_id']}>"
                        )

                if 0 < (appt_time - now).total_seconds() <= 1800:
                    channel = guild.get_channel(config.LOG_CHANNEL_ID)
                    if channel:
                        await channel.send(
                            f"{role.mention} ⏰ 30 minute reminder for <@{appt['user_id']}>"
                        )
            except:
                continue

async def setup(bot):
    await bot.add_cog(Appointments(bot))
