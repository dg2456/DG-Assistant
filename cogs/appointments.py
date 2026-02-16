import discord
from discord import app_commands
from discord.ext import commands, tasks
import json, os, uuid, asyncio, datetime

# IDs from your request
DG_ROLE = 1472681773577142459
DG_USER = 891113337579008061
CLIENT_ROLE = 1472691982357758032
OFFICE_ROLE = 1472691907959460077
LOG_CHAN = 1472691188233539645
ARCHIVE_CHAN = 1472765152138100787

class AppointmentSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data_path = "data/appointments.json"
        self.active_timers = {}
        self.load_data()
        self.daily_check.start()

    def load_data(self):
        if not os.path.exists("data"): os.makedirs("data")
        try:
            with open(self.data_path, "r") as f: self.data = json.load(f)
        except: self.data = {"slots": [], "bookings": {}}

    def save_data(self):
        with open(self.data_path, "w") as f: json.dump(self.data, f, indent=4)

    @app_commands.command(name="appointment_set", description="DG Only: Set a time slot")
    async def appt_set(self, itxn: discord.Interaction, date: str, time: str):
        if not itxn.user.get_role(DG_ROLE): return await itxn.response.send_message("No permission.", ephemeral=True)
        self.data["slots"].append(f"{date} @ {time}")
        self.save_data()
        await itxn.response.send_message(f"Added: {date} @ {time}", ephemeral=True)

    @app_commands.command(name="make_appointment", description="Book a session with DG")
    async def make_appt(self, itxn: discord.Interaction):
        if not self.data["slots"]: return await itxn.response.send_message("No open slots.", ephemeral=True)
        
        embed = discord.Embed(title="DG Appointment Booking", color=discord.Color.blue())
        desc = "\n".join([f"{i+1}. {s}" for i, s in enumerate(self.data['slots'])])
        embed.description = f"**Available Times:**\n{desc}"
        
        await itxn.response.send_message(embed=embed, view=BookingFlow(self), ephemeral=True)

    @app_commands.command(name="appointment_open", description="DG Only: Open office")
    async def appt_open(self, itxn: discord.Interaction, appt_id: str):
        appt = self.data["bookings"].get(appt_id)
        if not appt: return await itxn.response.send_message("Invalid ID.", ephemeral=True)
        
        member = itxn.guild.get_member(appt["user_id"])
        if member:
            role = itxn.guild.get_role(OFFICE_ROLE)
            await member.add_roles(role)
            await member.send(f"DG has opened your appointment. Join his office in 5 mins or it will be removed.")
            await itxn.response.send_message(f"Office opened for {member.display_name}", ephemeral=True)
            
            self.active_timers[appt_id] = True
            await asyncio.sleep(300)
            if self.active_timers.get(appt_id):
                await member.remove_roles(role)
                await itxn.followup.send(f"Time expired for {member.mention}. Role removed.")

    @app_commands.command(name="appointment_start", description="DG Only: Start the session")
    async def appt_start(self, itxn: discord.Interaction, appt_id: str):
        if appt_id in self.active_timers:
            self.active_timers[appt_id] = False
            await itxn.response.send_message(f"Session {appt_id} started. Timer stopped.", ephemeral=True)

    @tasks.loop(minutes=30)
    async def daily_check(self):
        today = datetime.datetime.now().strftime("%m/%d")
        for aid, info in self.data["bookings"].items():
            if info["time"].startswith(today) and not info.get("notified"):
                chan = self.bot.get_channel(LOG_CHAN)
                if chan:
                    await chan.send(f"<@{DG_USER}> Appointment today! ID: {aid} with <@{info['user_id']}>")
                    info["notified"] = True
                    self.save_data()

# --- UI FOR BOOKING ---
class BookingFlow(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog
        self.selected_slot = None
        self.selected_type = None

    @discord.ui.button(label="1. Select Day & Type", style=discord.ButtonStyle.grey)
    async def step_one(self, itxn: discord.Interaction, btn: discord.ui.Button):
        modal = BookingModal(self)
        await itxn.response.send_modal(modal)

class BookingModal(discord.ui.Modal, title="Booking Details"):
    day_num = discord.ui.TextInput(label="Slot Number (e.g. 1)", placeholder="Enter the number from the list")
    type = discord.ui.TextInput(label="Type (Commission or Long Term)", placeholder="Commission / Long Term Development")
    extra = discord.ui.TextInput(label="Extra Info", style=discord.TextStyle.paragraph, required=False)

    def __init__(self, view):
        super().__init__()
        self.view = view

    async name(self): pass # placeholder

    async def on_submit(self, itxn: discord.Interaction):
        try:
            idx = int(self.day_num.value) - 1
            slot = self.view.cog.data["slots"][idx]
        except:
            return await itxn.response.send_message("Invalid slot number!", ephemeral=True)

        aid = str(uuid.uuid4())[:8]
        self.view.cog.data["bookings"][aid] = {
            "user_id": itxn.user.id,
            "time": slot,
            "type": self.type.value,
            "info": self.extra.value
        }
        self.view.cog.data["slots"].pop(idx)
        self.view.cog.save_data()

        role = itxn.guild.get_role(CLIENT_ROLE)
        await itxn.user.add_roles(role)
        await itxn.user.send(f"Appointment Confirmed! ID: {aid}\nTime: {slot}")
        await itxn.response.send_message(f"✅ Confirmed! ID: `{aid}` sent to DMs.", ephemeral=True)

async def setup(bot): await bot.add_cog(AppointmentSystem(bot))
