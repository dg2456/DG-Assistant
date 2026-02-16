import discord
from discord import app_commands
from discord.ext import commands, tasks
from discord.ui import Select, View, Button, Modal, TextInput
import json
import os
import uuid
import datetime
import asyncio

# --- CONFIGURATION ---
DG_ROLE_ID = 1472681773577142459
DG_USER_ID = 891113337579008061
APPT_ROLE_ID = 1472691982357758032
OFFICE_ACCESS_ROLE_ID = 1472691907959460077

LOG_CHANNEL_ID = 1472691188233539645
ARCHIVE_CHANNEL_ID = 1472765152138100787

# Saves inside your data folder
DATA_FILE = "data/appointments.json"

class AppointmentSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.load_data()
        self.check_appointments_loop.start()
        self.active_timers = {} # Tracks 5-minute timers for removal

    def load_data(self):
        # Create data folder if it doesn't exist
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

    # --- 1. SET APPOINTMENT SLOTS (DG ONLY) ---
    @app_commands.command(name="appointment_set", description="Set an open appointment slot (DG Only)")
    async def appointment_set(self, interaction: discord.Interaction, date_str: str, time_str: str):
        """Input Example: 10/25 5:00 PM"""
        if not self.is_dg(interaction):
            return await interaction.response.send_message("Missing Permissions.", ephemeral=True)
        
        full_slot_str = f"{date_str} {time_str}"
        self.data["open_slots"].append(full_slot_str)
        self.save_data()
        await interaction.response.send_message(f"Added open slot: `{full_slot_str}`", ephemeral=True)

    # --- 2. MAKE APPOINTMENT FLOW ---
    @app_commands.command(name="make_appointment", description="View available times and book DG")
    async def make_appointment(self, interaction: discord.Interaction):
        # Filter available slots
        slots = self.data["open_slots"]
        if not slots:
            return await interaction.response.send_message("No open slots available right now.", ephemeral=True)

        # Create the initial view
        view = BookingView(self, slots[:25]) # Limit 25 for select menu
        
        # Create the display Embed
        embed = discord.Embed(title="📅 Book an Appointment", description="Please select a date and time from the dropdown below to begin.", color=discord.Color.blue())
        
        # Display available slots purely for visibility if needed, though they are in the dropdown
        slot_text = "\n".join([f"• {s}" for s in slots[:10]])
        if len(slots) > 10: slot_text += "\n...and more"
        embed.add_field(name="Available Times", value=slot_text or "Check dropdown")

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    # --- 3. CANCEL APPOINTMENT ---
    @app_commands.command(name="cancel_appointment", description="Cancel your appointment")
    async def cancel_appointment(self, interaction: discord.Interaction, appointment_id: str):
        if appointment_id in self.data["appointments"]:
            appt = self.data["appointments"][appointment_id]
            
            # Check ownership or DG permission
            if str(interaction.user.id) == str(appt["user_id"]) or self.is_dg(interaction):
                # Return slot to pool
                self.data["open_slots"].append(appt["time"])
                del self.data["appointments"][appointment_id]
                self.save_data()
                
                # Remove Role
                role = interaction.guild.get_role(APPT_ROLE_ID)
                member = interaction.guild.get_member(appt["user_id"])
                if member and role:
                    await member.remove_roles(role)

                await interaction.response.send_message(f"Appointment `{appointment_id}` cancelled.", ephemeral=True)
            else:
                await interaction.response.send_message("You do not own this appointment.", ephemeral=True)
        else:
            await interaction.response.send_message("Appointment ID not found.", ephemeral=True)

    # --- 4. DG MANAGEMENT COMMANDS ---
    @app_commands.command(name="appointment_open", description="Open office access for user (DG Only)")
    async def appointment_open(self, interaction: discord.Interaction, appointment_id: str):
        if not self.is_dg(interaction): return await interaction.response.send_message("No permission.", ephemeral=True)
        
        if appointment_id not in self.data["appointments"]:
            return await interaction.response.send_message("ID not found.", ephemeral=True)

        appt = self.data["appointments"][appointment_id]
        member = interaction.guild.get_member(appt["user_id"])
        
        if not member:
            return await interaction.response.send_message("User is no longer in the server.", ephemeral=True)

        # Give Access Role
        role = interaction.guild.get_role(OFFICE_ACCESS_ROLE_ID)
        if role: await member.add_roles(role)

        # DM User
        try:
            await member.send("DG has opened your appointment. Please join his office in **5 minutes** or your appointment will be removed.")
        except:
            await interaction.response.send_message("Role added, but could not DM user (DMs closed).", ephemeral=True)

        await interaction.response.send_message(f"Opened appointment for {member.mention}. 5-minute timer started.", ephemeral=True)

        # Start Timer
        self.active_timers[appointment_id] = "waiting"
        await asyncio.sleep(300) # 5 Minutes

        # Timer Check
        if self.active_timers.get(appointment_id) == "waiting":
            if role: await member.remove_roles(role)
            await interaction.followup.send(f"⚠️ Timer expired for {member.mention}. Access role removed.")
            del self.active_timers[appointment_id]

    @app_commands.command(name="appointment_start", description="Stop the removal timer (DG Only)")
    async def appointment_start(self, interaction: discord.Interaction, appointment_id: str):
        if not self.is_dg(interaction): return await interaction.response.send_message("No permission.", ephemeral=True)

        if appointment_id in self.active_timers:
            self.active_timers[appointment_id] = "started"
            await interaction.response.send_message(f"✅ Appointment `{appointment_id}` started. Timer stopped, role will stay.", ephemeral=True)
        else:
            await interaction.response.send_message("No active timer found for this ID.", ephemeral=True)

    @app_commands.command(name="appointment_end", description="End and Archive (DG Only)")
    async def appointment_end(self, interaction: discord.Interaction, appointment_id: str):
        if not self.is_dg(interaction): return await interaction.response.send_message("No permission.", ephemeral=True)

        if appointment_id not in self.data["appointments"]:
            return await interaction.response.send_message("ID not found.", ephemeral=True)

        appt = self.data["appointments"][appointment_id]
        member = interaction.guild.get_member(appt["user_id"])
        
        # Remove Roles
        access_role = interaction.guild.get_role(OFFICE_ACCESS_ROLE_ID)
        appt_role = interaction.guild.get_role(APPT_ROLE_ID)
        
        if member:
            if access_role: await member.remove_roles(access_role)
            if appt_role: await member.remove_roles(appt_role)

        # Move Log to Archive
        log_channel = self.bot.get_channel(LOG_CHANNEL_ID)
        archive_channel = self.bot.get_channel(ARCHIVE_CHANNEL_ID)
        
        # Attempt to find the message in log channel
        if log_channel:
            async for message in log_channel.history(limit=50):
                if message.embeds and str(appointment_id) in (message.embeds[0].footer.text or ""):
                    embed = message.embeds[0]
                    embed.title = f"Appointment Ended: {appointment_id}"
                    embed.color = discord.Color.greyple()
                    if archive_channel: await archive_channel.send(embed=embed)
                    await message.delete()
                    break
        
        # Cleanup Data
        del self.data["appointments"][appointment_id]
        if appointment_id in self.active_timers:
            del self.active_timers[appointment_id]
        self.save_data()

        await interaction.response.send_message(f"Appointment `{appointment_id}` ended and archived.", ephemeral=True)

    # --- BACKGROUND LOOP ---
    @tasks.loop(minutes=1)
    async def check_appointments_loop(self):
        # Checks if today is the day of an appointment
        now = datetime.datetime.now()
        current_date_str = now.strftime("%m/%d") # e.g. "10/25"

        for appt_id, data in self.data["appointments"].items():
            # If already logged, skip
            if data.get("logged_today"):
                continue

            # Check if the appointment date string starts with today's date
            # data["time"] format is "10/25 5:00 PM"
            if data["time"].startswith(current_date_str):
                
                log_channel = self.bot.get_channel(LOG_CHANNEL_ID)
                if log_channel:
                    embed = discord.Embed(title="🔔 Appointment Today", color=discord.Color.green())
                    embed.add_field(name="Client", value=f"<@{data['user_id']}>")
                    embed.add_field(name="Time", value=data['time'])
                    embed.add_field(name="Type", value=data['type'])
                    embed.add_field(name="Details", value=data['info'])
                    embed.set_footer(text=f"ID: {appt_id}")

                    # Ping DG
                    await log_channel.send(content=f"<@{DG_USER_ID}> You have an appointment today!", embed=embed)

                # Mark as logged so we don't spam
                self.data["appointments"][appt_id]["logged_today"] = True
                self.save_data()

    @check_appointments_loop.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()


# --- UI CLASSES ---

class BookingView(View):
    def __init__(self, cog, slots):
        super().__init__(timeout=300)
        self.cog = cog
        self.selected_slot = None
        self.selected_type = None
        self.info_details = "None provided"

        # 1. Date Select Menu
        self.date_select = Select(
            placeholder="Select a Date & Time",
            options=[discord.SelectOption(label=s, value=s) for s in slots]
        )
        self.date_select.callback = self.date_callback
        self.add_item(self.date_select)

        # 2. Type Buttons
        self.btn_comm = Button(label="Commission", style=discord.ButtonStyle.secondary, disabled=True)
        self.btn_ltd = Button(label="Long Term Dev", style=discord.ButtonStyle.secondary, disabled=True)
        
        self.btn_comm.callback = self.comm_callback
        self.btn_ltd.callback = self.ltd_callback
        
        self.add_item(self.btn_comm)
        self.add_item(self.btn_ltd)

        # 3. Details Button
        self.btn_details = Button(label="Add Extra Details", style=discord.ButtonStyle.primary, disabled=True)
        self.btn_details.callback = self.details_callback
        self.add_item(self.btn_details)

        # 4. Confirm Button
        self.btn_confirm = Button(label="Confirm Booking", style=discord.ButtonStyle.success, disabled=True)
        self.btn_confirm.callback = self.confirm_callback
        self.add_item(self.btn_confirm)

    async def update_view(self, interaction: discord.Interaction):
        # Enable Type buttons if slot is selected
        if self.selected_slot:
            self.btn_comm.disabled = False
            self.btn_ltd.disabled = False
        
        # Highlight selected type
        if self.selected_type == "Commission":
            self.btn_comm.style = discord.ButtonStyle.primary
            self.btn_ltd.style = discord.ButtonStyle.secondary
        elif self.selected_type == "Long Term Development":
            self.btn_comm.style = discord.ButtonStyle.secondary
            self.btn_ltd.style = discord.ButtonStyle.primary

        # Enable Details and Confirm if type is selected
        if self.selected_type:
            self.btn_details.disabled = False
            self.btn_confirm.disabled = False

        await interaction.response.edit_message(view=self)

    async def date_callback(self, interaction: discord.Interaction):
        self.selected_slot = self.date_select.values[0]
        await self.update_view(interaction)

    async def comm_callback(self, interaction: discord.Interaction):
        self.selected_type = "Commission"
        await self.update_view(interaction)

    async def ltd_callback(self, interaction: discord.Interaction):
        self.selected_type = "Long Term Development"
        await self.update_view(interaction)

    async def details_callback(self, interaction: discord.Interaction):
        modal = DetailsModal(self)
        await interaction.response.send_modal(modal)

    async def confirm_callback(self, interaction: discord.Interaction):
        # Final Check: Is slot still valid?
        if self.selected_slot not in self.cog.data["open_slots"]:
            return await interaction.response.edit_message(content="❌ This time slot was just taken by someone else!", view=None, embed=None)

        # Remove slot
        self.cog.data["open_slots"].remove(self.selected_slot)
        
        # Generate ID
        appt_id = uuid.uuid4().hex[:6]
        
        # Save Data
        self.cog.data["appointments"][appt_id] = {
            "user_id": interaction.user.id,
            "time": self.selected_slot,
            "type": self.selected_type,
            "info": self.info_details,
            "logged_today": False
        }
        self.cog.save_data()

        # Give Role
        role = interaction.guild.get_role(APPT_ROLE_ID)
        if role: await interaction.user.add_roles(role)

        # DM User
        try:
            await interaction.user.send(
                f"✅ **Appointment Confirmed!**\n"
                f"**ID:** `{appt_id}`\n"
                f"**Time:** {self.selected_slot}\n"
                f"**Type:** {self.selected_type}\n"
                f"**Details:** {self.info_details}"
            )
        except:
            pass # Cant DM

        await interaction.response.edit_message(content=f"✅ **Booked!** check your DMs.\nAppointment ID: `{appt_id}`", view=None, embed=None)


class DetailsModal(Modal):
    def __init__(self, view):
        super().__init__(title="Extra Details")
        self.view = view
        self.info = TextInput(label="Information for DG", style=discord.TextStyle.paragraph, required=True)
        self.add_item(self.info)

    async def on_submit(self, interaction: discord.Interaction):
        self.view.info_details = self.info.value
        await interaction.response.defer() # Acknowledge without sending message
        # We don't need to re-render the view here, the user just clicks Confirm next
