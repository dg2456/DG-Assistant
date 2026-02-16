import discord
from discord.ext import commands, tasks
from datetime import datetime
import json
import config

class Reminders(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_appointments.start()

    def load_data(self):
        try:
            with open("data/appointments.json", "r") as f:
                return json.load(f)
        except:
            return {}

    @tasks.loop(minutes=60)
    async def check_appointments(self):
        data = self.load_data()
        today = str(datetime.utcnow().date())

        channel = self.bot.get_channel(config.REMINDER_CHANNEL_ID)

        for id_, info in data.items():
            if info["day"] == today:
                await channel.send(
                    f"<@{config.PING_USER_ID}> Appointment `{id_}` is today!"
                )

async def setup(bot):
    await bot.add_cog(Reminders(bot))
