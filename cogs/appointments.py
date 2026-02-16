import discord
from discord import app_commands
from discord.ext import commands, tasks
from discord.ui import Select, View, Button, Modal, TextInput
import json
import os
import uuid
import datetime
import asyncio

# --- IDS CONFIGURATION ---
DG_ROLE_ID = 1472681773577142459
DG_USER_ID = 891113337579008061
APPT_ROLE_ID = 1472691982357758032
OFFICE_ACCESS_ROLE_ID = 1472691907959460077
LOG_CHANNEL_ID = 1472691188233539645
ARCHIVE_CHANNEL_ID = 1472765152138100787

DATA_FILE = "data.json"

class AppointmentSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.load_data()
        self.check_appointments_loop.start()
        # To track active timers to prevent role removal if start is called
        self.active_timers = {} 

    def load_data(self):
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
        """Format: MM/DD and HH:MM AM/PM"""
        if not self.is_dg(interaction):
            return await interaction.response.send_message("Missing Permissions.", ephemeral=True)
        
        full_slot_str = f"{date_str} {time_str}"
        self.data["open_slots"].append(full_slot_str)
        self.save_data()
        await interaction.response.send_message(f"Added open slot: `{full_slot_str}`", ephemeral=True)

    # --- 2. MAKE APPOINTMENT FLOW (EVERYONE) ---
    @app_commands.command(name="make_appointment", description="Book an appointment with DG")
    async def make_appointment(self, interaction: discord.Interaction):
        if not self.data["open_slots"]:
            return await interaction.response.send_message("No open slots available right now.", ephemeral=True)
        
        # Step 1: Select Date/Time
        select = Select(placeholder="Select a Date & Time", options=[
            discord.SelectOption(label=slot, value=slot) for slot in self.data["open_slots"][:25] # Discord limit 25
        ])

        async def select_callback(inter: discord.Interaction):
            selected_slot = select.values[0]
            
            # Step 2: Select Type (Buttons)
            view_type = View()
            btn_comm = Button(label="Commission", style=discord.ButtonStyle.primary)
            btn_ltd = Button(label="Long Term Development", style=discord.ButtonStyle.primary)

            async def type_callback(btn_inter: discord.Interaction, type_name: str):
                # Step 3: Modal for details
                modal = AppointmentModal(self, selected_slot, type_name)
                await btn_inter.response.send_modal(modal)

            btn_comm.callback = lambda i: type_callback(i, "Commission")
            btn_ltd.callback = lambda i: type_callback(i, "Long Term Development")
            
            view_type.add_item(btn_comm)
            view_type.add_item(btn_ltd)
            
            await inter.response.edit_message(content=f"Selected: **{selected_slot}**. Now select the type:", view=view_type, embed=None)

        select.callback = select_callback
        view = View()
        view.add_item(select)
        
        embed = discord.Embed(title="Book an Appointment", description="Please select a time from the list below.", color=discord.Color.gold())
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    # --- 3. CANCEL APPOINTMENT ---
    @app_commands.command(name="cancel_appointment", description="Cancel an existing appointment")
    async def cancel_appointment(self, interaction: discord.Interaction, appointment_id: str):
        if appointment_id in self.data["appointments"]:
            appt = self.data["appointments"][appointment_id]
            # Verify user owns this appointment or is DG
            if str(interaction.user.id) == str(appt["user_id"]) or self.is_dg(interaction):
                # Add slot back to open slots? Optional, but good practice
                self.data["open_slots"].append(appt["time"])
                del self.data["appointments"][appointment_id]
                self.save_data()
                
                # Try to remove role
                try:
                    role = interaction.guild.get_role(APPT_ROLE_ID)
                    member = interaction.guild.get_member(appt["user_id"])
                    if member and role:
                        await member.remove_roles(role)
                except:
                    pass

                await interaction.response.send_message(f"Appointment `{appointment_id}` cancelled.", ephemeral=True)
            else:
                await interaction.response.send_message("You do not own this appointment.", ephemeral=True)
        else:
            await interaction.response.send_message("Appointment ID not found.", ephemeral=True)

    # --- 4. APPOINTMENT MANAGEMENT (DG ONLY) ---
    
    @app_commands.command(name="appointment_open", description="Open access for a user (DG Only)")
    async def appointment_open(self, interaction: discord.Interaction, appointment_id: str):
        if not self.is_dg(interaction): return
        
        if appointment_id not in self.data["appointments"]:
            return await interaction.response.send_message("ID not found.", ephemeral=True)

        appt = self.data["appointments"][appointment_id]
        user_id = appt["user_id"]
        member = interaction.guild.get_member(user_id)
        
        if not member:
            return await interaction.response.send_message("User not found in server.", ephemeral=True)

        role = interaction.guild.get_role(OFFICE_ACCESS_ROLE_ID)
        await member.add_roles(role)

        # DM The user
        try:
            await member.send("DG has opened your appointment. Please join his office in **5 minutes** or your appointment will be removed.")
        except:
            await interaction.response.send_message("Role given, but could not DM user.", ephemeral=True)

        await interaction.response.send_message(f"Opened appointment for {member.mention}. Timer started.", ephemeral=True)

        # Start 5 minute timer
        self.active_timers[appointment_id] = "waiting"
        await asyncio.sleep(300) # 5 minutes

        # Check if status changed to 'started'
        if self.active_timers.get(appointment_id) == "waiting":
            await member.remove_roles(role)
            await interaction.followup.send(f"Time expired for {member.mention}. Role removed.")
            del self.active_timers[appointment_id]

    @app_commands.command(name="appointment_start", description="Stop the removal timer (DG Only)")
    async def appointment_start(self, interaction: discord.Interaction, appointment_id: str):
        if not self.is_dg(interaction): return

        if appointment_id in self.active_timers:
            self.active_timers[appointment_id] = "started"
            await interaction.response.send_message(f"Appointment `{appointment_id}` started. Role will stay.", ephemeral=True)
        else:
            await interaction.response.send_message("No active timer found for this ID.", ephemeral=True)

    @app_commands.command(name="appointment_end", description="End appointment and archive (DG Only)")
    async def appointment_end(self, interaction: discord.Interaction, appointment_id: str):
        if not self.is_dg(interaction): return

        if appointment_id not in self.data["appointments"]:
            return await interaction.response.send_message("ID not found.", ephemeral=True)

        appt = self.data["appointments"][appointment_id]
        member = interaction.guild.get_member(appt["user_id"])
        
        # Remove Role
        role = interaction.guild.get_role(OFFICE_ACCESS_ROLE_ID)
        appt_role = interaction.guild.get_role(APPT_ROLE_ID)
        if member:
            if role: await member.remove_roles(role)
            if appt_role: await member.remove_roles(appt_role)

        # Move Log
        log_channel = self.bot.get_channel(LOG_CHANNEL_ID)
        archive_channel = self.bot.get_channel(ARCHIVE_CHANNEL_ID)
        
        # Find the message in log channel (naive search)
        found_msg = None
        async for message in log_channel.history(limit=50):
            if message.embeds and str(appointment_id) in message.embeds[0].footer.text:
                found_msg = message
                break
        
        if found_msg:
            embed = found_msg.embeds[0]
            embed.title = f"Appointment Ended: {appointment_id}"
            embed.color = discord.Color.greyple()
            await archive_channel.send(embed=embed)
            await found_msg.delete()
        
        # Clean up data
        del self.data["appointments"][appointment_id]
        if appointment_id in self.active_timers:
            del self.active_timers[appointment_id]
        self.save_data()

        await interaction.response.send_message(f"Appointment `{appointment_id}` ended and archived.", ephemeral=True)

    # --- BACKGROUND TASK ---
    @tasks.loop(minutes=1)
    async def check_appointments_loop(self):
        # Format current time to match "MM/DD HH:MM AM/PM"
        # Note: This requires exact string matching. 
        # Since user manually inputs "MM/DD HH:MM", we check if today matches that string.
        # Ideally, we would parse objects, but string matching is safer for manual input variations.
        
        now = datetime.datetime.now()
        # We need to construct the date string based on how the user enters it.
        # Assuming user enters "10/25 5:00 PM", we need to check if that matches now.
        # This is tricky without strict formatting. 
        
        # Logic: Iterate through all appointments. If the string date is "today", log it.
        # To prevent spamming, we need a "logged" flag in the json, but for now we'll just check.
        
        current_date_str = now.strftime("%m/%d") # e.g., 02/16
        
        for appt_id, data in self.data["appointments"].items():
            if data.get("logged_today") is True:
                continue

            time_str = data["time"] # "02/16 5:00 PM"
            
            if time_str.startswith(current_date_str):
                # It is the day of the appointment
                dg_user = self.bot.get_user(DG_USER_ID)
                log_channel = self.bot.get_channel(LOG_CHANNEL_ID)
                
                embed = discord.Embed(title="📅 Appointment Alert", description=f"Appointment ID: {appt_id}", color=discord.Color.brand_green())
                embed.add_field(name="Client", value=f"<@{data['user_id']}>")
                embed.add_field(name="Time", value=time_str)
                embed.add_field(name="Type", value=data['type'])
                embed.add_field(name="Info", value=data['info'])
                embed.set_footer(text=f"ID: {appt_id}")
                
                if log_channel:
                    await log_channel.send(content=f"<@{DG_USER_ID}> Appointment today!", embed=embed)
                
                # Mark as logged so it doesn't spam every minute of that day
                self.data["appointments"][appt_id]["logged_today"] = True
                self.save_data()

    @check_appointments_loop.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

# --- HELPER MODAL CLASS ---
class AppointmentModal(Modal):
    def __init__(self, cog, slot, appt_type):
        super().__init__(title="Appointment Details")
        self.cog = cog
        self.slot = slot
        self.appt_type = appt_type
        
        self.info = TextInput(label="Additional Information", style=discord.TextStyle.paragraph, required=True)
        self.add_item(self.info)

    async def on_submit(self, interaction: discord.Interaction):
        # Remove the slot from open slots
        if self.slot in self.cog.data["open_slots"]:
            self.cog.data["open_slots"].remove(self.slot)
        else:
            return await interaction.response.send_message("This slot was just taken by someone else!", ephemeral=True)

        # Create ID and Save
        appt_id = uuid.uuid4().hex[:6]
        
        self.cog.data["appointments"][appt_id] = {
            "user_id": interaction.user.id,
            "time": self.slot,
            "type": self.appt_type,
            "info": self.info.value,
            "logged_today": False
        }
        self.cog.save_data()

        # Give Role
        role = interaction.guild.get_role(APPT_ROLE_ID)
        if role:
            await interaction.user.add_roles(role)

        # DM User
        try:
            await interaction.user.send(f"Appointment Confirmed!\n**ID:** `{appt_id}`\n**Time:** {self.slot}\n**Type:** {self.appt_type}")
        except:
            pass

        # Internal Log (Immediate log of creation)
        # Note: The prompt asks to log "when it's the day of", which is handled by the loop.
        # But usually, you want a confirmation immediately too. 
        # We will just send the ephemeral confirmation as requested.
        
        await interaction.response.send_message(f"Appointment booked! Check your DMs. ID: `{appt_id}`", ephemeral=True)

async def setup(bot):
    await bot.add_cog(AppointmentSystem(bot))
