import discord
from discord.ext import commands
import gettext
from teamo import Teamo

bot = commands.Bot(command_prefix=discord.ext.commands.when_mentioned)

bot.add_cog(Teamo(bot))

@bot.event
async def on_ready():
    print(f"Connected as {bot}")

bot.run('NjU3ODk2MjExODkzODQ2MDI2.Xf33mA.Dix23qOplArx3glV4RTTAqisqvg')
