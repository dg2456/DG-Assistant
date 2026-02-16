import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import uuid
from datetime import datetime, timedelta
import config

APPOINTMENTS_FILE = "data/appointments.json"
SLOTS_FILE = "data/slots.json"

ACTIVE_ROLE_ID = 1472691907959460077
STAFF_ROLE_ID = config.STAFF_ROLE_ID
STAFF_PING_ROLE_ID = 1472681773577142459
TODAY_CHANNEL_ID = 1472691188233539645
COMPLETED_CHANNEL_ID = 1472765152138100787


# ---------------- JSON ---------------- #

def load_json(path):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except:
        return {}

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=4)


# ---------------- VIEW ---------------- #

class AppointmentView(discord.ui.View):
    def __init__(self, user, slot_id):
        super().__init__(timeout=300)
        self.user = user
        self.slot_id = slot_id
        self.type_selected = None

    @discord.ui.select(
        placeholder="Select Appointment Type",
        options=[
            discord.SelectOption(label="Commission"),
            discord.SelectOption(label="Long Term Development")
        ]
    )
    async def select_type(self, interaction: discord.Interaction, select: discord.ui.Select):
        if interaction.user != self.user:
            return await interaction.response.send_message("Not yours.", ephemeral=True)

        self.type_selected = select.values[0]
        await interaction.response.send_message(
            f"Selected: {self.type_selected}",
            ephemeral=True
        )

    @discord.ui.button(label="Confirm Appointment", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):

        await interaction.response.defer(ephemeral=True)

        if interaction.user != self.user:
            return await interaction.followup.send("Not yours.", ephemeral=True)

        if not self.type_selected:
            return await interaction.followup.send("Select a type first.", ephemeral=True)

        appointments = load_json(APPOINTMENTS_FILE)
        slots = load_json(SLOTS_FILE)

        # Prevent double booking
        for data in appointments.values():
            if data["user_id"] == interaction.user.id:
                return await interaction.followup.send(
                    "You already have an appointment booked.",
                    ephemeral=True
                )

        if self.slot_id not in slots:
            return await interaction.followup.send("Slot already taken.", ephemeral=True)

        appointment_id = str(uuid.uuid4())[:8]

        embed = discord.Embed(title="📅 New Appointment", color=discord.Color.green())
        embed.add_field(name="ID", value=appointment_id)
        embed.add_field(name="User", value=interaction.user.mention)
        embed.add_field(name="Slot", value=slots[self.slot_id])
        embed.add_field(name="Type", value=self.type_selected)

        channel = interaction.guild.get_channel(TODAY_CHANNEL_ID)
        message = await channel.send(
            f"<@&{STAFF_PING_ROLE_ID}>",
            embed=embed
        )

        appointments[appointment_id] = {
            "user_id": interaction.user.id,
            "slot": slots[self.slot_id],
            "type": self.type_selected,
            "status": "booked",
            "guild_id": interaction.guild.id,
            "message_id": message.id,
            "reminded": False
        }

        del slots[self.slot_id]

        save_json(APPOINTMENTS_FILE, appointments)
        save_json(SLOTS_FILE, slots)

        await interaction.followup.send("Appointment booked.", ephemeral=True)
        self.stop()


# ---------------- COG ---------------- #

class Appointments(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.auto_cancel_loop.start()
        self.daily_reminder_loop.start()

    # ---------------- ADD SLOT ---------------- #

    @app_commands.command(name="appointment_set")
    async def appointment_set(self, interaction: discord.Interaction, date: str, time: str):

        await interaction.response.defer(ephemeral=True)

        if not any(role.id == STAFF_ROLE_ID for role in interaction.user.roles):
            return await interaction.followup.send("Not authorized.", ephemeral=True)

        slots = load_json(SLOTS_FILE)
        slot_id = str(len(slots) + 1)

        slots[slot_id] = f"{date} {time}"
        save_json(SLOTS_FILE, slots)

        await interaction.followup.send(f"Slot added: {date} {time}", ephemeral=True)

    # ---------------- MAKE APPOINTMENT ---------------- #

    @app_commands.command(name="make_appointment")
    async def make_appointment(self, interaction: discord.Interaction):

        await interaction.response.defer(ephemeral=True)

        slots = load_json(SLOTS_FILE)

        if not slots:
            return await interaction.followup.send("No slots available.", ephemeral=True)

        description = ""
        for k, v in slots.items():
            description += f"**{k}.** {v}\n"

        embed = discord.Embed(
            title="Available Appointments",
            description=description,
            color=discord.Color.blurple()
        )

        await interaction.followup.send(embed=embed, ephemeral=True)
        await interaction.followup.send(
            "Reply with the number of the slot you want.",
            ephemeral=True
        )

        def check(m):
            return m.author == interaction.user and m.channel == interaction.channel

        try:
            msg = await self.bot.wait_for("message", timeout=60, check=check)
            chosen = msg.content.strip()

            if chosen not in slots:
                return await interaction.followup.send("Invalid slot.", ephemeral=True)

            view = AppointmentView(interaction.user, chosen)
            await interaction.followup.send(
                "Complete your appointment:",
                view=view,
                ephemeral=True
            )
        except:
            await interaction.followup.send("Timed out.", ephemeral=True)

    # ---------------- AUTO CANCEL ---------------- #

    @tasks.loop(seconds=60)
    async def auto_cancel_loop(self):
        appointments = load_json(APPOINTMENTS_FILE)
        now = datetime.utcnow()

        changed = False

        for aid, data in list(appointments.items()):
            if data.get("status") == "open":
                opened_at = datetime.fromisoformat(data["opened_at"])
                if now - opened_at > timedelta(minutes=5):
                    guild = self.bot.get_guild(data["guild_id"])
                    if guild:
                        member = guild.get_member(data["user_id"])
                        role = guild.get_role(ACTIVE_ROLE_ID)
                        if member and role:
                            await member.remove_roles(role)
                    del appointments[aid]
                    changed = True

        if changed:
            save_json(APPOINTMENTS_FILE, appointments)

    # ---------------- DAILY REMINDER ---------------- #

    @tasks.loop(minutes=5)
    async def daily_reminder_loop(self):
        appointments = load_json(APPOINTMENTS_FILE)
        today = datetime.utcnow().strftime("%m/%d")

        for aid, data in appointments.items():
            if today in data.get("slot", "") and not data.get("reminded"):
                guild = self.bot.get_guild(data["guild_id"])
                channel = guild.get_channel(TODAY_CHANNEL_ID)

                try:
                    message = await channel.fetch_message(data["message_id"])
                    await message.reply(
                        f"<@&{STAFF_PING_ROLE_ID}> 📅 This appointment is TODAY."
                    )
                    data["reminded"] = True
                    save_json(APPOINTMENTS_FILE, appointments)
                except:
                    pass


async def setup(bot):
    await bot.add_cog(Appointments(bot))
