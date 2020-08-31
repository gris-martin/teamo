import os
import sys

from discord.ext import commands

from teamo import Teamo


bot = commands.Bot(command_prefix=commands.when_mentioned)
bot.add_cog(Teamo(bot))


@bot.event
async def on_ready():
    print(f"Connected as {bot}")

token = os.environ["TEAMO_BOT_TOKEN"]
if (token is None):
    print("Missing bot token. Set the TEAMO_BOT_TOKEN environment variable to the bot token found on the Discord Developer Portal.")
    sys.exit(1)

bot.run(token)
