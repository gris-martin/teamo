import argparse
import os
import sys

from discord.ext import commands

from teamo.app import Teamo

def main():
    parser = argparse.ArgumentParser(description='Start the Teamo bot.')
    parser.add_argument(
        "--database",
        dest="database",
        type=str,
        default="db/teamo.db",
        help="specify the location of the database to use (default: db/teamo.db)"
    )
    args = parser.parse_args()

    bot = commands.Bot(command_prefix=commands.when_mentioned)
    bot.add_cog(Teamo(bot, args.database))

    @bot.event
    async def on_ready():
        print(f"Connected as {bot}")

    token = os.environ["TEAMO_BOT_TOKEN"]
    if (token is None):
        print("Missing bot token. Set the TEAMO_BOT_TOKEN environment variable to the bot token found on the Discord Developer Portal.")
        sys.exit(1)

    bot.run(token)

if __name__ == "__main__":
    main()
