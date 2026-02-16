import discord
from discord import app_commands
from discord.ext import commands
import uuid
import datetime

# --- CONFIGURATION ---
DG_ROLE_ID = 1472681773577142459
WORK_LOG_CHANNEL = 1472695020720099390
WORK_ARCHIVE_CHANNEL = 1472695669889433691

class WorkSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def is_dg(self, interaction: discord.Interaction):
        return interaction.user.get_role(DG_ROLE_ID) is not None

    @app_commands.command(name="work_add", description="Log new work (DG Only)")
    @app_commands.describe(user="The client", due_date="Optional due date", robux="Amount made")
    async def work_add(self, interaction: discord.Interaction, user: discord.Member, info: str, robux: int, due_date: str = "None"):
        if not self.is_dg(interaction):
            return await interaction.response.send_message("Missing Permissions.", ephemeral=True)

        work_id = uuid.uuid4().hex[:6]
        
        embed = discord.Embed(title=f"New Work Started: {work_id}", color=discord.Color.blue())
        embed.add_field(name="Client", value=user.mention, inline=True)
        embed.add_field(name="Due Date", value=due_date, inline=True)
        embed.add_field(name="Robux", value=str(robux), inline=True)
        embed.add_field(name="Details", value=info, inline=False)
        embed.set_footer(text=f"Work ID: {work_id}")

        channel = self.bot.get_channel(WORK_LOG_CHANNEL)
        msg = await channel.send(f"{user.mention} Work started.", embed=embed)
        
        await interaction.response.send_message(f"Work logged with ID `{work_id}` in {channel.mention}", ephemeral=True)

    @app_commands.command(name="work_complete", description="Mark work as complete (DG Only)")
    async def work_complete(self, interaction: discord.Interaction, work_id: str):
        if not self.is_dg(interaction):
            return await interaction.response.send_message("Missing Permissions.", ephemeral=True)

        # In a real bot, you would fetch the message via DB. 
        # Here we scan the active channel for the embed (Simple method)
        log_channel = self.bot.get_channel(WORK_LOG_CHANNEL)
        archive_channel = self.bot.get_channel(WORK_ARCHIVE_CHANNEL)
        
        target_message = None
        async for message in log_channel.history(limit=50):
            if message.embeds and message.embeds[0].footer.text == f"Work ID: {work_id}":
                target_message = message
                break
        
        if target_message:
            embed = target_message.embeds[0]
            embed.color = discord.Color.green()
            embed.title = f"Work Completed: {work_id}"
            embed.timestamp = datetime.datetime.now()
            
            await archive_channel.send(content=target_message.content, embed=embed)
            await target_message.delete()
            await interaction.response.send_message(f"Work `{work_id}` moved to archive.", ephemeral=True)
        else:
            await interaction.response.send_message(f"Could not find Work ID `{work_id}` in the active log channel.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(WorkSystem(bot))
