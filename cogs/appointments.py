import discord
from discord import app_commands
from discord.ext import commands, tasks
from discord.ui import View, Modal, TextInput, Button
import json, os, uuid, asyncio, datetime
import traceback

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

    # --- DG COMMANDS ---

    @app_commands.command(name="appointment_set", description="DG Only: Set a time slot")
    async def appt_set(self, itxn: discord.Interaction, date: str, time: str):
        await itxn.response.defer(ephemeral=True)
        try:
            if not self.is_dg(itxn.user):
                return await itxn.followup.send("❌ Access Denied.")
            
            self.data["slots"].append(f"{date} @ {time}")
            self.save_data()
            await itxn.followup.send(f"✅ Slot Saved: `{date} @ {time}`")
        except Exception as e:
            await itxn.followup.send(f"⚠️ Error in set: {e}")
            print(traceback.format_exc())

    @app_commands.command(name="appointment_end", description="DG Only: Close session & Archive log")
    async def appt_end(self, itxn: discord.Interaction, appt_id: str):
        await itxn.response.defer(ephemeral=True)
        try:
            if not self.is_dg(itxn.user): return await itxn.followup.send("❌ Access Denied.")

            appt = self.data["bookings"].get(appt_id)
            if not appt: return await itxn.followup.send(f"❌ ID `{appt_id}` not found.")

            # Attempt to fetch member (more reliable than get_member)
            try:
                member = await itxn.guild.fetch_member(appt["user_id"])
                o_role = itxn.guild.get_role(OFFICE_ROLE_ID)
                c_role = itxn.guild.get_role(CLIENT_ROLE_ID)
                if member:
                    if o_role: await member.remove_roles(o_role)
                    if c_role: await member.remove_roles(c_role)
            except:
                print("Could not update roles - member might have left.")

            # Archive Logic
            log_chan = self.bot.get_channel(LOG_CHAN_ID)
            archive_chan = self.bot.get_channel(ARCHIVE_CHAN_ID)
            
            found_msg = False
            if log_chan and archive_chan:
                async for msg in log_chan.history(limit=100):
                    if msg.embeds and msg.embeds[0].footer and appt_id in (msg.embeds[0].footer.text or ""):
                        await archive_chan.send(embed=msg.embeds[0])
                        await msg.delete()
                        found_msg = True
                        break

            del self.data["bookings"][appt_id]
            self.save_data()
            await itxn.followup.send(f"✅ Appointment `{appt_id}` ended and archived.")
            
        except Exception as e:
            await itxn.followup.send(f"⚠️ Error in end: {e}")
            print(traceback.format_exc())

    # --- PUBLIC COMMANDS ---

    @app_commands.command(name="make_appointment", description="Book a session with DG")
    async def make_appt(self, itxn: discord.Interaction):
        try:
            if not self.data.get("slots"):
                return await itxn.response.send_message("❌ No slots open.", ephemeral=True)
            
            embed = discord.Embed(title="DG Appointment Booking", color=discord.Color.blue())
            desc = "\n".join([f"**{i+1}.** {s}" for i, s in enumerate(self.data['slots'])])
            embed.description = f"**Available Times:**\n{desc}\n\nSelect a number below."
            
            await itxn.response.send_message(embed=embed, view=BookingFlow(self), ephemeral=True)
        except Exception as e:
            print(f"Error in make_appt: {e}")

    @tasks.loop(minutes=30)
    async def daily_check(self):
        # Daily logic remains same
        pass

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
    appt_type = TextInput(label="Type", placeholder="Commission or Long Term")
    extra = TextInput(label="Extra Info", style=discord.TextStyle.paragraph, required=False)

    def __init__(self, cog):
        super().__init__()
        self.cog = cog

    async def on_submit(self, itxn: discord.Interaction):
        await itxn.response.defer(ephemeral=True)
        try:
            idx = int(self.day_num.value) - 1
            if idx < 0 or idx >= len(self.cog.data["slots"]):
                return await itxn.followup.send("❌ Invalid slot number.")
            
            slot = self.cog.data["slots"][idx]
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
        except Exception as e:
            await itxn.followup.send(f"⚠️ Error in modal: {e}")

async def setup(bot):
    await bot.add_cog(AppointmentSystem(bot))
