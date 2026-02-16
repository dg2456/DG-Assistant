import discord
from discord import app_commands
from discord.ext import commands, tasks
from discord.ui import Select, View, Button, Modal, TextInput
import json
import os
import uuid
import datetime
import asyncio

# --- CONFIGURATION (Ensure these match your Server) ---
DG_ROLE_ID = 1472681773577142459
DG_USER_ID = 891113337579008061
APPT_ROLE_ID = 1472691982357758032
OFFICE_ACCESS_ROLE_ID = 1472691907959460077
LOG_CHANNEL_ID = 1472691188233539645
ARCHIVE_CHANNEL_ID = 1472765152138100787

DATA_FILE = "data/appointments.json"

class AppointmentSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.load_data()
        self.check_appointments_loop.start()
        self.active_timers = {}

    def load_data(self):
        if not os.path.exists("data"):
            os.makedirs("data")
        if not os.path.exists(DATA_FILE):
            self.data = {"open_slots": [], "appointments": {}}
            self.save_data()
        else:
            with open(DATA_FILE, "r") as f:
                self.data = json.load(f)

    def save_data(self):
        with open(DATA_FILE, "w") as f:
            json.dump(self.data, f, indent=4)

    def is_dg(self, interaction: discord.Interaction):
        return interaction.user.get_role(DG_ROLE_ID) is not None

    @app_commands.command(name="appointment_set", description="Set an open appointment slot (DG Only)")
    async def appointment_set(self, interaction: discord.Interaction, date: str, time: str):
        if not self.is_dg(interaction):
            return await interaction.response.send_message("Missing Permissions.", ephemeral=True)
        slot = f"{date} {time}"
        self.data["open_slots"].append(slot)
        self.save_data()
        await interaction.response.send_message(f"Added slot: `{slot}`", ephemeral=True)

    @app_commands.command(name="make_appointment", description="Book an appointment")
    async def make_appointment(self, interaction: discord.Interaction):
        slots = self.data["open_slots"]
        if not slots:
            return await interaction.response.send_message("No slots available.", ephemeral=True)
        view = BookingView(self, slots[:25])
        embed = discord.Embed(title="Book an Appointment", color=discord.Color.blue())
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="appointment_open", description="Open access (DG Only)")
    async def appointment_open(self, interaction: discord.Interaction, appt_id: str):
        if not self.is_dg(interaction): return
        appt = self.data["appointments"].get(appt_id)
        if not appt: return await interaction.response.send_message("Invalid ID.", ephemeral=True)
        
        member = interaction.guild.get_member(appt["user_id"])
        role = interaction.guild.get_role(OFFICE_ACCESS_ROLE_ID)
        if member and role:
            await member.add_roles(role)
            await interaction.response.send_message(f"Opened for {member.mention}.", ephemeral=True)
            self.active_timers[appt_id] = "waiting"
            await asyncio.sleep(300)
            if self.active_timers.get(appt_id) == "waiting":
                await member.remove_roles(role)
                del self.active_timers[appt_id]

    @app_commands.command(name="appointment_start", description="Confirm user arrived (DG Only)")
    async def appointment_start(self, interaction: discord.Interaction, appt_id: str):
        if appt_id in self.active_timers:
            self.active_timers[appt_id] = "started"
            await interaction.response.send_message("Timer stopped. Role kept.", ephemeral=True)

    @tasks.loop(minutes=1)
    async def check_appointments_loop(self):
        now = datetime.datetime.now().strftime("%m/%d")
        for aid, info in self.data["appointments"].items():
            if info["time"].startswith(now) and not info.get("logged_today"):
                chan = self.bot.get_channel(LOG_CHANNEL_ID)
                if chan:
                    await chan.send(f"<@{DG_USER_ID}> Appointment today with <@{info['user_id']}>!")
                    self.data["appointments"][aid]["logged_today"] = True
                    self.save_data()

# --- UI CLASSES ---
class BookingView(View):
    def __init__(self, cog, slots):
        super().__init__()
        self.cog = cog
        self.slot = None
        self.type = None
        select = Select(placeholder="Choose Time", options=[discord.SelectOption(label=s, value=s) for s in slots])
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        self.slot = interaction.data['values'][0]
        view = TypeView(self.cog, self.slot)
        await interaction.response.edit_message(content=f"Time: {self.slot}. Pick Type:", view=view, embed=None)

class TypeView(View):
    def __init__(self, cog, slot):
        super().__init__()
        self.cog, self.slot = cog, slot

    @discord.ui.button(label="Commission", style=discord.ButtonStyle.primary)
    async def comm(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(DetailsModal(self.cog, self.slot, "Commission"))

    @discord.ui.button(label="Long Term Dev", style=discord.ButtonStyle.primary)
    async def ltd(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(DetailsModal(self.cog, self.slot, "Long Term Development"))

class DetailsModal(Modal, title="Extra Info"):
    info = TextInput(label="Details", style=discord.TextStyle.paragraph)
    def __init__(self, cog, slot, atype):
        super().__init__()
        self.cog, self.slot, self.atype = cog, slot, atype

    async def on_submit(self, interaction: discord.Interaction):
        aid = uuid.uuid4().hex[:6]
        self.cog.data["appointments"][aid] = {"user_id": interaction.user.id, "time": self.slot, "type": self.atype, "info": self.info.value}
        if self.slot in self.cog.data["open_slots"]: self.cog.data["open_slots"].remove(self.slot)
        self.cog.save_data()
        
        role = interaction.guild.get_role(APPT_ROLE_ID)
        if role: await interaction.user.add_roles(role)
        await interaction.user.send(f"Confirmed! ID: {aid}")
        await interaction.response.edit_message(content=f"Booked! ID: {aid}", view=None)

# --- THE MISSING LINK: SETUP FUNCTION ---
async def setup(bot):
    await bot.add_cog(AppointmentSystem(bot))
