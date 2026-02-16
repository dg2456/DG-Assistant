import discord
from discord import app_commands
from discord.ext import commands, tasks
from discord.ui import View, Modal, TextInput
import json, os, uuid, asyncio, datetime

# --- CONFIGURATION ---
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

    def is_dg(self, member):
        return any(role.id == DG_ROLE_ID for role in member.roles)

    @app_commands.command(name="make_appointment", description="Book a session with DG")
    async def make_appt(self, itxn: discord.Interaction):
        # We respond immediately to the interaction
        if not self.data.get("slots"):
            return await itxn.response.send_message("❌ No slots available.", ephemeral=True)
        
        embed = discord.Embed(title="📅 DG Appointment Booking", color=discord.Color.blue())
        desc = "\n".join([f"**{i+1}.** {s}" for i, s in enumerate(self.data['slots'])])
        embed.description = f"**Available Times:**\n{desc}\n\nClick below to book."
        
        await itxn.response.send_message(embed=embed, view=BookingFlow(self), ephemeral=True)

    @app_commands.command(name="appointment_open", description="DG Only: Open office (ID Required)")
    async def appt_open(self, itxn: discord.Interaction, appt_id: str):
        # DEFER FIRST: Stops the "not responding" error
        await itxn.response.defer(ephemeral=True)
        
        if not self.is_dg(itxn.user):
            return await itxn.followup.send("❌ No permission.")

        appt = self.data["bookings"].get(appt_id)
        if not appt: return await itxn.followup.send("❌ Invalid ID.")
        
        member = itxn.guild.get_member(appt["user_id"])
        role = itxn.guild.get_role(OFFICE_ROLE_ID)
        
        if member and role:
            await member.add_roles(role)
            try: await member.send(f"🔔 DG has opened your appointment. Join his office in 5 minutes.")
            except: pass
            
            await itxn.followup.send(f"✅ Opened for {member.mention}. 5m timer started.")
            self.active_timers[appt_id] = True
            await asyncio.sleep(300)
            
            if self.active_timers.get(appt_id) is True:
                await member.remove_roles(role)
                await itxn.followup.send(f"⏰ Time expired for {member.mention}. Access removed.")

    @app_commands.command(name="appointment_end", description="DG Only: Close session & archive (ID Required)")
    async def appt_end(self, itxn: discord.Interaction, appt_id: str):
        # DEFER FIRST: Moving messages takes time
        await itxn.response.defer(ephemeral=True)

        if not self.is_dg(itxn.user):
            return await itxn.followup.send("❌ No permission.")

        appt = self.data["bookings"].get(appt_id)
        if not appt: return await itxn.followup.send("❌ Invalid ID.")

        member = itxn.guild.get_member(appt["user_id"])
        o_role = itxn.guild.get_role(OFFICE_ROLE_ID)
        c_role = itxn.guild.get_role(CLIENT_ROLE_ID)

        if member:
            if o_role: await member.remove_roles(o_role)
            if c_role: await member.remove_roles(c_role)

        # Move logs from Log Channel to Archive Channel
        log_chan = self.bot.get_channel(LOG_CHAN_ID)
        archive_chan = self.bot.get_channel(ARCHIVE_CHAN_ID)
        
        if log_chan and archive_chan:
            async for msg in log_chan.history(limit=100):
                if msg.embeds and appt_id in (msg.embeds[0].footer.text or ""):
                    await archive_chan.send(embed=msg.embeds[0])
                    await msg.delete()
                    break

        del self.data["bookings"][appt_id]
        self.save_data()
        await itxn.followup.send(f"✅ Appointment `{appt_id}` ended and archived.")

    @tasks.loop(minutes=30)
    async def daily_check(self):
        # ... logic as before ...
        pass

# --- UI CLASSES ---
class BookingFlow(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="Book Now", style=discord.ButtonStyle.primary)
    async def book_btn(self, itxn: discord.Interaction, btn: discord.ui.Button):
        # Modals don't need deferral because the Modal itself IS the response
        await itxn.response.send_modal(BookingModal(self.cog))

class BookingModal(discord.ui.Modal, title="Appointment Details"):
    day_num = TextInput(label="Slot Number", placeholder="e.g. 1")
    appt_type = TextInput(label="Type", placeholder="Commission/Dev")
    extra = TextInput(label="Extra Info", style=discord.TextStyle.paragraph, required=False)

    def __init__(self, cog):
        super().__init__()
        self.cog = cog

    async def on_submit(self, itxn: discord.Interaction):
        # DEFER FIRST: Logic + Role adding takes time
        await itxn.response.defer(ephemeral=True)
        
        try:
            idx = int(self.day_num.value) - 1
            slot = self.cog.data["slots"][idx]
        except:
            return await itxn.followup.send("❌ Invalid slot number.")

        aid = str(uuid.uuid4())[:8]
        self.cog.data["bookings"][aid] = {
            "user_id": itxn.user.id, "time": slot,
            "type": self.appt_type.value, "info": self.extra.value, "notified": False
        }
        self.cog.data["slots"].pop(idx)
        self.cog.save_data()

        role = itxn.guild.get_role(CLIENT_ROLE_ID)
        if role: await itxn.user.add_roles(role)

        await itxn.followup.send(f"✅ Success! Your ID is `{aid}`. Check your DMs.")
        try:
            await itxn.user.send(f"✅ Appointment Confirmed!\n**ID:** `{aid}`\n**Time:** {slot}")
        except: pass

async def setup(bot):
    await bot.add_cog(AppointmentSystem(bot))
