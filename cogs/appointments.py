import discord
from discord import app_commands
from discord.ext import commands, tasks
from discord.ui import Select, View, Button, Modal, TextInput
import json, os, uuid, asyncio, datetime

# --- CONFIGURATION ---
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

    @app_commands.command(name="appointment_set", description="DG Only: Set a time slot (MM/DD and Time)")
    async def appt_set(self, itxn: discord.Interaction, date: str, time: str):
        if not itxn.user.get_role(DG_ROLE): 
            return await itxn.response.send_message("No permission.", ephemeral=True)
        self.data["slots"].append(f"{date} @ {time}")
        self.save_data()
        await itxn.response.send_message(f"Added slot: `{date} @ {time}`", ephemeral=True)

    @app_commands.command(name="make_appointment", description="Book a session with DG")
    async def make_appt(self, itxn: discord.Interaction):
        if not self.data["slots"]: 
            return await itxn.response.send_message("No open slots available.", ephemeral=True)
        
        embed = discord.Embed(title="DG Appointment Booking", color=discord.Color.blue())
        desc = "\n".join([f"**{i+1}.** {s}" for i, s in enumerate(self.data['slots'])])
        embed.description = f"**Available Times:**\n{desc}\n\nClick the button below to claim a slot."
        
        await itxn.response.send_message(embed=embed, view=BookingFlow(self), ephemeral=True)

    @app_commands.command(name="appointment_open", description="DG Only: Open office and alert user")
    async def appt_open(self, itxn: discord.Interaction, appt_id: str):
        appt = self.data["bookings"].get(appt_id)
        if not appt: return await itxn.response.send_message("Invalid ID.", ephemeral=True)
        
        member = itxn.guild.get_member(appt["user_id"])
        if member:
            role = itxn.guild.get_role(OFFICE_ROLE)
            await member.add_roles(role)
            try:
                await member.send(f"DG has opened your appointment. Please join his office in 5 minutes or your appointment will be removed.")
            except: pass
            
            await itxn.response.send_message(f"Office opened for {member.display_name}. 5-minute timer started.", ephemeral=True)
            
            self.active_timers[appt_id] = True
            await asyncio.sleep(300) # 5 minutes
            
            # Check if /appointment_start was used
            if self.active_timers.get(appt_id) is True:
                await member.remove_roles(role)
                await itxn.followup.send(f"⏰ Time expired for {member.mention}. Access role removed.")

    @app_commands.command(name="appointment_start", description="DG Only: Confirm user arrival (stops timer)")
    async def appt_start(self, itxn: discord.Interaction, appt_id: str):
        if appt_id in self.active_timers:
            self.active_timers[appt_id] = False # Timer stopped
            await itxn.response.send_message(f"Session `{appt_id}` started. Timer disabled.", ephemeral=True)

    @app_commands.command(name="appointment_end", description="DG Only: End and archive appointment")
    async def appt_end(self, itxn: discord.Interaction, appt_id: str):
        appt = self.data["bookings"].get(appt_id)
        if not appt: return await itxn.response.send_message("Invalid ID.", ephemeral=True)

        member = itxn.guild.get_member(appt["user_id"])
        role = itxn.guild.get_role(OFFICE_ROLE)
        client_role = itxn.guild.get_role(CLIENT_ROLE)

        if member:
            if role: await member.remove_roles(role)
            if client_role: await member.remove_roles(client_role)

        # Move logs
        log_chan = self.bot.get_channel(LOG_CHAN)
        archive_chan = self.bot.get_channel(ARCHIVE_CHAN)
        
        async for msg in log_chan.history(limit=50):
            if msg.embeds and appt_id in msg.embeds[0].footer.text:
                await archive_chan.send(embed=msg.embeds[0])
                await msg.delete()
                break

        del self.data["bookings"][appt_id]
        self.save_data()
        await itxn.response.send_message(f"Appointment `{appt_id}` ended and archived.", ephemeral=True)

    @tasks.loop(minutes=30)
    async def daily_check(self):
        today = datetime.datetime.now().strftime("%m/%d")
        for aid, info in self.data["bookings"].items():
            if info["time"].startswith(today) and not info.get("notified"):
                chan = self.bot.get_channel(LOG_CHAN)
                if chan:
                    embed = discord.Embed(title="Appointment Today!", color=discord.Color.green())
                    embed.add_field(name="User", value=f"<@{info['user_id']}>")
                    embed.add_field(name="Time", value=info['time'])
                    embed.set_footer(text=f"ID: {aid}")
                    await chan.send(content=f"<@{DG_USER}> You have an appointment today!", embed=embed)
                    info["notified"] = True
                    self.save_data()

# --- UI CLASSES ---
class BookingFlow(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="Click to Book", style=discord.ButtonStyle.primary)
    async def book_btn(self, itxn: discord.Interaction, btn: discord.ui.Button):
        await itxn.response.send_modal(BookingModal(self.cog))

class BookingModal(discord.ui.Modal, title="Appointment Details"):
    day_num = discord.ui.TextInput(label="Which Number? (e.g. 1)", placeholder="Enter the number from the list above")
    appt_type = discord.ui.TextInput(label="Type", placeholder="Commission or Long Term Development")
    extra = discord.ui.TextInput(label="Additional Information", style=discord.TextStyle.paragraph, required=False)

    def __init__(self, cog):
        super().__init__()
        self.cog = cog

    async def on_submit(self, itxn: discord.Interaction):
        try:
            idx = int(self.day_num.value) - 1
            slot = self.cog.data["slots"][idx]
        except:
            return await itxn.response.send_message("Invalid slot number! Please refer to the list numbers.", ephemeral=True)

        aid = str(uuid.uuid4())[:8]
        self.cog.data["bookings"][aid] = {
            "user_id": itxn.user.id,
            "time": slot,
            "type": self.appt_type.value,
            "info": self.extra.value,
            "notified": False
        }
        self.cog.data["slots"].pop(idx)
        self.cog.save_data()

        role = itxn.guild.get_role(CLIENT_ROLE)
        if role: await itxn.user.add_roles(role)

        try:
            await itxn.user.send(f"✅ Appointment Confirmed!\n**ID:** `{aid}`\n**Time:** {slot}\n**Type:** {self.appt_type.value}")
        except: pass

        await itxn.response.send_message(f"✅ Success! Your Appointment ID is `{aid}`. Check your DMs.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(AppointmentSystem(bot))
