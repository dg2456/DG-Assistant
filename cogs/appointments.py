import discord
from discord import app_commands
from discord.ext import commands, tasks
from discord.ui import View, Modal, TextInput, Button
import json, os, uuid, asyncio, datetime

# --- CONFIGURATION (Locked to your provided IDs) ---
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

    # --- DG COMMANDS (OPTIMIZED SPEED) ---

    @app_commands.command(name="appointment_set", description="DG Only: Set a time slot (MM/DD and Time)")
    async def appt_set(self, itxn: discord.Interaction, date: str, time: str):
        # 1. Instant acknowledgment to Discord
        await itxn.response.defer(ephemeral=True)
        
        if not self.is_dg(itxn.user):
            return await itxn.followup.send("❌ Access Denied.")
        
        # 2. Process data
        self.data["slots"].append(f"{date} @ {time}")
        self.save_data()
        
        # 3. Final confirmation
        await itxn.followup.send(f"✅ Slot Saved: `{date} @ {time}`")

    @app_commands.command(name="appointment_open", description="DG Only: Grant office access (ID Required)")
    async def appt_open(self, itxn: discord.Interaction, appt_id: str):
        await itxn.response.defer(ephemeral=True)
        if not self.is_dg(itxn.user): return await itxn.followup.send("❌ Access Denied.")

        appt = self.data["bookings"].get(appt_id)
        if not appt: return await itxn.followup.send("❌ Appointment ID not found.")
        
        member = itxn.guild.get_member(appt["user_id"])
        role = itxn.guild.get_role(OFFICE_ROLE_ID)
        
        if member and role:
            await member.add_roles(role)
            await itxn.followup.send(f"✅ Access granted to {member.mention}. 5m timer started.")
            
            try: await member.send(f"DG has opened your appointment. Join his office within 5 mins.")
            except: pass
            
            self.active_timers[appt_id] = True
            await asyncio.sleep(300)
            
            if self.active_timers.get(appt_id) is True:
                await member.remove_roles(role)
                await itxn.followup.send(f"⏰ Access expired for {member.mention}.")

    @app_commands.command(name="appointment_start", description="DG Only: Lock in access (Stops the 5m timer)")
    async def appt_start(self, itxn: discord.Interaction, appt_id: str):
        if not self.is_dg(itxn.user): return await itxn.response.send_message("❌ Access Denied.", ephemeral=True)
        
        if appt_id in self.active_timers:
            self.active_timers[appt_id] = False
            await itxn.response.send_message(f"✅ Session started. Timer disabled for `{appt_id}`.", ephemeral=True)
        else:
            await itxn.response.send_message("❌ No active timer for this ID.", ephemeral=True)

    @app_commands.command(name="appointment_end", description="DG Only: Close session & Archive log (ID Required)")
    async def appt_end(self, itxn: discord.Interaction, appt_id: str):
        # 1. Immediate Deferral (Crucial because history search is slow)
        await itxn.response.defer(ephemeral=True)
        
        if not self.is_dg(itxn.user): return await itxn.followup.send("❌ Access Denied.")

        appt = self.data["bookings"].get(appt_id)
        if not appt: return await itxn.followup.send("❌ ID not found.")

        # Remove Roles
        member = itxn.guild.get_member(appt["user_id"])
        o_role = itxn.guild.get_role(OFFICE_ROLE_ID)
        c_role = itxn.guild.get_role(CLIENT_ROLE_ID)
        if member:
            if o_role: await member.remove_roles(o_role)
            if c_role: await member.remove_roles(c_role)

        # Archive Logic
        log_chan = self.bot.get_channel(LOG_CHAN_ID)
        archive_chan = self.bot.get_channel(ARCHIVE_CHAN_ID)
        
        found_msg = False
        if log_chan and archive_chan:
            async for msg in log_chan.history(limit=100):
                if msg.embeds and appt_id in (msg.embeds[0].footer.text or ""):
                    await archive_chan.send(embed=msg.embeds[0])
                    await msg.delete()
                    found_msg = True
                    break

        del self.data["bookings"][appt_id]
        self.save_data()
        
        status = "and archived" if found_msg else "(log message not found, but data cleared)"
        await itxn.followup.send(f"✅ Appointment `{appt_id}` ended {status}.")

    # --- PUBLIC COMMANDS ---

    @app_commands.command(name="make_appointment", description="Book a session with DG")
    async def make_appt(self, itxn: discord.Interaction):
        # Embeds are fast, but we ensure we respond to the itxn first
        if not self.data.get("slots"):
            return await itxn.response.send_message("❌ No slots open.", ephemeral=True)
        
        embed = discord.Embed(title="DG Appointment Booking", color=discord.Color.blue())
        desc = "\n".join([f"**{i+1}.** {s}" for i, s in enumerate(self.data['slots'])])
        embed.description = f"**Available Times:**\n{desc}\n\nSelect a number and type below."
        
        await itxn.response.send_message(embed=embed, view=BookingFlow(self), ephemeral=True)

    @tasks.loop(minutes=30)
    async def daily_check(self):
        today = datetime.datetime.now().strftime("%m/%d")
        for aid, info in self.data["bookings"].items():
            if info["time"].startswith(today) and not info.get("notified"):
                chan = self.bot.get_channel(LOG_CHAN_ID)
                if chan:
                    embed = discord.Embed(title="Appointment Today!", color=discord.Color.green())
                    embed.add_field(name="User", value=f"<@{info['user_id']}>")
                    embed.add_field(name="Time", value=info['time'])
                    embed.set_footer(text=f"ID: {aid}")
                    await chan.send(content=f"<@{DG_USER_ID}> Appointment Alert!", embed=embed)
                    info["notified"] = True
                    self.save_data()

# --- UI LOGIC ---

class BookingFlow(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="Book Now", style=discord.ButtonStyle.primary)
    async def book_btn(self, itxn: discord.Interaction, btn: Button):
        await itxn.response.send_modal(BookingModal(self.cog))

class BookingModal(discord.ui.Modal, title="Booking Details"):
    day_num = TextInput(label="Slot Number", placeholder="e.g. 1")
    appt_type = TextInput(label="Type", placeholder="Commission or Long Term Development")
    extra = TextInput(label="Extra Info", style=discord.TextStyle.paragraph, required=False)

    def __init__(self, cog):
        super().__init__()
        self.cog = cog

    async def on_submit(self, itxn: discord.Interaction):
        # 1. Instant deferral for the Modal submission
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

        # Add Role
        role = itxn.guild.get_role(CLIENT_ROLE_ID)
        if role: await itxn.user.add_roles(role)

        await itxn.followup.send(f"✅ Success! Your Appointment ID is `{aid}`. Check your DMs.")
        try:
            await itxn.user.send(f"✅ Appointment Confirmed!\n**ID:** `{aid}`\n**Time:** {slot}\n**Type:** {self.appt_type.value}")
        except: pass

async def setup(bot):
    await bot.add_cog(AppointmentSystem(bot))
