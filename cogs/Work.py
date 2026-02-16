import discord
from discord import app_commands
from discord.ext import commands
import json, os, uuid

DG_ROLE = 1472681773577142459
WORK_LOG = 1472695020720099390
WORK_DONE = 1472695669889433691

class WorkSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.path = "data/work_data.json"

    @app_commands.command(name="work_add", description="DG Only: Add work log")
    async def work_add(self, itxn: discord.Interaction, user: discord.User, robux: int, info: str, due: str = "N/A"):
        if not itxn.user.get_role(DG_ROLE): return
        
        wid = str(uuid.uuid4())[:6]
        embed = discord.Embed(title=f"Work Log: {wid}", color=discord.Color.orange())
        embed.add_field(name="Client", value=user.mention)
        embed.add_field(name="Amount", value=f"{robux} Robux")
        embed.add_field(name="Due", value=due)
        embed.description = info
        
        msg = await self.bot.get_channel(WORK_LOG).send(embed=embed)
        await itxn.response.send_message(f"Logged work {wid}", ephemeral=True)

    @app_commands.command(name="work_complete", description="DG Only: Complete work")
    async def work_comp(self, itxn: discord.Interaction, work_id: str):
        # Implementation to find embed and move it
        chan_old = self.bot.get_channel(WORK_LOG)
        chan_new = self.bot.get_channel(WORK_DONE)
        
        async for msg in chan_old.history(limit=100):
            if msg.embeds and work_id in msg.embeds[0].title:
                await chan_new.send(embed=msg.embeds[0])
                await msg.delete()
                return await itxn.response.send_message(f"Work {work_id} archived.", ephemeral=True)
        await itxn.response.send_message("Work ID not found.", ephemeral=True)

async def setup(bot): await bot.add_cog(WorkSystem(bot))
