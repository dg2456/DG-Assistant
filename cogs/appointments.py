import discord
from discord import app_commands
from discord.ext import commands, tasks
from discord.ui import View, Modal, TextInput
import json, os, uuid, asyncio, datetime

# --- CONFIGURATION (Ensure these IDs are 100% correct) ---
DG_ROLE_ID = 1472681773577142459
DG_USER_ID = 891113337579008061
CLIENT_ROLE_ID = 1472691982357758032
OFFICE_ROLE_ID = 1472691907959460077
LOG_CHAN_ID = 1472691188233539645
ARCHIVE_CHAN_ID = 1472765152138100787

class AppointmentSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data_path = "data/appointments.json"
        self.active_timers = {}
        self.load_data()
        if not self.daily_check.is_running():
            self.daily_check.start()

    def load_data(self):
        if not os.path.exists("data"): os.makedirs("data")
        try:
            with open(self.data_path, "r") as f: self.data = json.load(f)
        except: self.data = {"slots": [], "bookings": {}}

    def save_data(self):
        with open(self.data_path, "w") as f: json.dump(self.data, f, indent=4)

    # Helper to check permissions without crashing
    def is_dg(self, member):
        return any(role.id == DG_ROLE_ID for role in member.roles)

    @app_commands.command(name="appointment_set", description="DG Only: Set a time slot")
    async def appt_set(self, itxn: discord.Interaction, date: str, time: str):
        if not self.is_dg(itxn.user):
            return await itxn.response.send_message("❌ No permission.", ephemeral=True)
        
        self.data["slots"].append(f"{date} @ {time}")
        self.save_data()
        await itxn.response.send_message(f"✅ Added slot: `{date} @ {time}`", ephemeral=True)

    @app_commands.command(name="make_appointment", description="Book a session")
    async def make_appt(self, itxn: discord.Interaction):
        if not self.data.get("slots"):
            return await itxn.response.send_message("❌ No slots available.", ephemeral=True)
        
        embed = discord.Embed(title="📅 DG Appointment Booking", color=discord.Color.blue())
        desc = "\n".join([f"**{i+1}.** {s}" for i, s in enumerate(self.data['slots'])])
        embed.description = f"**Available Times:**\n{desc}\n\nClick below to book."
        
        await itxn.response.send_message(embed=embed, view=BookingFlow(self), ephemeral=True)

    @app_commands.command(name="appointment_open", description="DG Only: Open office")
    async def appt_open(self, itxn: discord.Interaction, appt_id: str):
        # 1. Immediate Deferral (Prevents "not responding")
        await itxn.response.defer(ephemeral=True)
        
        appt = self.data["bookings"].get(appt_id)
        if not appt: return await itxn.followup.send("❌ Invalid ID.")
        
        member = itxn.guild.get_member(appt["user_id"])
        role = itxn.guild.get_role(OFFICE_ROLE_ID)
        
        if member and role:
            await member.add_roles(role)
            try: await member.send("🔔 DG has opened your appointment. Join in 5m.")
            except: pass
            
            await itxn.followup.send(f"✅ Opened for {member.mention}. 5m timer started.")
            self.active_timers[appt_id] = True
            await asyncio.sleep(300)
            
            if self.active_timers.get(appt_id) is True:
                await member.remove_roles(role)
                await itxn.followup.send(f"⏰ Time expired for {member.mention}.")

    @app_commands.command(name="appointment_start", description="Stop the timer")
    async def appt_start(self, itxn: discord.Interaction, appt_id: str):
        if appt_id in self.active_timers:
            self.active_timers[appt_id] = False
            await itxn.response.send_message(f"✅ Session `{appt_id}` started.", ephemeral=True)
        else:
            await itxn.response.send_message("❌ ID not found in active timers.", ephemeral=True)

    @tasks.loop(minutes=30)
    async def daily_check(self):
        # Task logic remains the same
        pass

# --- UI CLASSES ---
class BookingFlow(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="Book Now", style=discord.ButtonStyle.primary)
    async def book_btn(self, itxn: discord.Interaction, btn: discord.ui.Button):
        # Modal is a "response," so it doesn't need a deferral beforehand
        await itxn.response.send_modal(BookingModal(self.cog))

class BookingModal(discord.ui.Modal, title="Appointment Details"):
    day_num = TextInput(label="Slot Number", placeholder="e.g. 1")
    appt_type = TextInput(label="Type", placeholder="Commission/Dev")
    extra = TextInput(label="Extra Info", style=discord.TextStyle.paragraph, required=False)

    def __init__(self, cog):
        super().__init__()
        self.cog = cog

    async def on_submit(self, itxn: discord.Interaction):
        # 1. Defer Modal Submission
        await itxn.response.defer(ephemeral=True)
        
        try:
            idx = int(self.day_num.value) - 1
            slot = self.cog.data["slots"][idx]
        except:
            return await itxn.followup.send("❌ Invalid slot number.")

        aid = str(uuid.uuid4())[:8]
        self.cog.data["bookings"][aid] = {
            "user_id": itxn.user.id, "time": slot,
            "type": self.appt_type.value, "notified": False
        }
        self.cog.data["slots"].pop(idx)
        self.cog.save_data()

        role = itxn.guild.get_role(CLIENT_ROLE_ID)
        if role: await itxn.user.add_roles(role)

        # Use followup because we deferred
        await itxn.followup.send(f"✅ Success! ID: `{aid}`")

async def setup(bot):
    await bot.add_cog(AppointmentSystem(bot))
