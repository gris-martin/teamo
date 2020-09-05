import re
from dateparser.search import search_dates
from datetime import datetime, timedelta
from typing import List, Dict
import time
import asyncio
import traceback
from pathlib import Path
import os
import sys
import argparse

# Third party imports
import discord
from discord.ext import commands

# Internal imports
from teamo import models, utils, config, database, teams
from teamo.utils import send_and_print


class Teamo(commands.Cog):
    def __init__(self, bot, database_name):
        self.bot = bot
        Path("db").mkdir(exist_ok=True)
        self.db = database.Database(database_name)
        asyncio.run(self.db.init())
        self.cached_messages: Dict[int, discord.Message] = dict()
        self.locks: Dict[int, asyncio.Lock] = dict()
        self.cancel_tasks: Dict[int, asyncio.Task] = dict()
        self.startup_done: asyncio.Event

    async def delete_entry(self, message_id: int):
        async with self.locks[message_id]:
            # Delete message from discord
            await self.cached_messages[message_id].delete()
            self.cached_messages[message_id] = None

            # Delete message from db
            await self.db.delete_entry(message_id)

    async def cancel_after(self, message_id: int):
        try:
            await asyncio.sleep(config.cancel_timeout)
        except asyncio.CancelledError:
            return
        await self.delete_entry(message_id)

    async def update_message(self, arg):
        if type(arg) is models.Entry:
            entry = arg
            message_id = entry.message_id
        elif type(arg) is int:
            entry = await self.db.get_entry(arg)
            message_id = arg
        else:
            raise Exception(
                f"Unknown argument type to update_message: {type(arg)}. Value: {arg}")
        is_cancelling = (
            message_id in self.cancel_tasks
            and self.cancel_tasks[message_id] is not None
            and not self.cancel_tasks[message_id].done()
        )
        try:
            message = self.cached_messages[message_id]
            await message.edit(embed=utils.create_embed(entry, is_cancelling))
        except discord.NotFound:
            await send_and_print(
                message.channel,
                f"WARNING: Attempted to update a message (ID: {entry.message_id}) that has already been deleted. Deleting message from database."
            )
            await self.db.delete_entry(entry.message_id)

    async def update_timer(self):
        while True:
            try:
                entries = await self.db.get_all_entries()
                for entry in entries:
                    await self.update_message(entry)
            except Exception:
                traceback.print_exc()
            await asyncio.sleep(config.update_interval)

    async def finish_timer(self):
        while True:
            entries = await self.db.get_all_entries()
            for entry in entries:
                if entry.start_date > datetime.now():
                    continue
                channel = await self.bot.fetch_channel(entry.channel_id)
                await channel.send(embed=teams.create_finish_embed(entry))
                await self.delete_entry(entry.message_id)
            await asyncio.sleep(config.finish_check_interval)

    async def sync_message(self, message_id: int):
        old_message = self.cached_messages[message_id]
        channel = old_message.channel
        self.cached_messages[message_id] = await channel.fetch_message(message_id)

    @commands.Cog.listener()
    async def on_connect(self):
        self.startup_done = asyncio.Event()

    @commands.Cog.listener()
    async def on_ready(self):
        entries = await self.db.get_all_entries()
        deleted_ids = []
        for entry in entries:
            channel_id = entry.channel_id
            message_id = entry.message_id
            try:
                channel: discord.TextChannel = self.bot.get_channel(channel_id)
                self.cached_messages[message_id] = await channel.fetch_message(message_id)
                self.locks[message_id] = asyncio.Lock()
            except discord.NotFound:
                print(
                    f"Discord message for database entry with message id {entry.message_id} does not exist. Removing entry from database.")
                deleted_ids.append(entry.message_id)

        await self.db.delete_entries(deleted_ids)

        if config.update_interval > 0:
            asyncio.create_task(self.update_timer())
        asyncio.create_task(self.finish_timer())
        self.startup_done.set()
        print("Teamo is ready!")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.member.bot:
            return

        # Check that reaction is either number or cancel emoji
        emoji: discord.PartialEmoji = payload.emoji
        if emoji.name not in utils.number_emojis and emoji.name != utils.cancel_emoji:
            return

        # Make sure the message reacted to is a Teamo message (exists in db)
        message_id = payload.message_id
        db_entry = await self.db.get_entry(message_id)
        if (db_entry is None):
            return

        await self.startup_done.wait()
        # If cancel emoji: Start cancel procedure
        if emoji.name == utils.cancel_emoji:
            cancel_task = asyncio.create_task(self.cancel_after(message_id))
            self.cancel_tasks[message_id] = cancel_task
            await self.update_message(message_id)
            await self.sync_message(message_id)
            return

        # If number emoji: Add or edit member, remove old reactions, update message
        async with self.locks[message_id]:
            num_players = utils.number_emojis.index(emoji.name) + 1
            member = models.Member(
                payload.member.id, num_players)
            previous_num_players = await self.db.edit_or_add_member(message_id, member)

            # Do not have to remove any reactions if the user wasn't registered before
            # or if the previous entry was the same as the current one (somehow)
            if previous_num_players is None or previous_num_players == num_players:
                await self.sync_message(message_id)
                await self.update_message(message_id)
                return

            # Update message
            await self.update_message(message_id)

            # Delete old reactions
            message = self.cached_messages[message_id]
            previous_emoji = utils.number_emojis[previous_num_players-1]
            old_reaction = next(
                (r for r in message.reactions if r.emoji == previous_emoji),
                None
            )
            await old_reaction.remove(payload.member)
            await self.sync_message(message_id)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        await self.startup_done.wait()
        message_id = payload.message_id
        await self.sync_message(message_id)

        if payload.user_id == self.bot.user.id:
            return

        # Check that reaction is either number or cancel emoji
        emoji: discord.PartialEmoji = payload.emoji
        if emoji.name not in utils.number_emojis and emoji.name != utils.cancel_emoji:
            return

        # Make sure the message reacted to is a Teamo message (exists in db)
        db_entry = await self.db.get_entry(message_id)
        if (db_entry is None):
            return

        # If cancel emoji: Abort cancel procedure
        if emoji.name == utils.cancel_emoji:
            cancel_task = self.cancel_tasks[message_id]
            if cancel_task is None or cancel_task.done():
                return
            cancel_task.cancel()
            self.cancel_tasks[message_id] = None
            await self.update_message(db_entry)

    @commands.command()
    async def create(self, ctx: discord.ext.commands.Context, *, arg: str):
        await self.startup_done.wait()
        # Parse arguments

        # TODO: Better date parsing
        args = re.match(r"^(\d+) (\d{1,2}:\d{2}) (.+)", arg)
        if (args is None):
            # TODO: Better error message
            await send_and_print(ctx.channel, "Invalid arguments to create command: {}".format(arg))
            return

        #   - Number of players
        max_players = int(args.group(1))
        n_guild_members = len(ctx.guild.members)
        if max_players < 2:
            await send_and_print(ctx.channel, "Number of players must be greater than 2.")
        if max_players > n_guild_members:
            await send_and_print(ctx.channel, "Number of players cannot be more than the number of members in the server, which is {}.".format(n_guild_members))
            return

        #   - Date
        date_str = args.group(2)
        date_results = search_dates(date_str)
        if date_results is None or len(date_results) == 0:
            await send_and_print(ctx.channel, "Invalid date: {}".format(date_str))
            return

        date = date_results[0][1]
        if date < datetime.now():
            date += timedelta(1)

        #   - Game
        game = args.group(3)
        max_game_chars = 30
        if len(game) > max_game_chars:
            await send_and_print(ctx.channel, "Game name too long, maximum length of game name is {} characters. Try again!".format(max_game_chars))
            return

        # Create message and send to Discord
        entry = models.Entry(
            game=game,
            start_date=date,
            max_players=max_players
        )
        embed = utils.create_embed(entry)
        message: discord.Message = await ctx.send(embed=embed)
        self.cached_messages[message.id] = message

        # Create database and runtime entries
        entry.message_id = message.id
        entry.channel_id = ctx.channel.id
        entry.server_id = ctx.guild.id
        await self.db.insert_entry(entry)

        # Update message again to show ID
        # Add reactions
        await self.update_message(entry)
        self.locks[message.id] = asyncio.Lock()
        async with self.locks[message.id]:
            for i in range(min(max_players-1, 10)):
                await message.add_reaction(utils.number_emojis[i])

            await message.add_reaction(utils.cancel_emoji)

        channel = self.bot.get_channel(entry.channel_id)
        self.cached_messages[message.id] = await channel.fetch_message(message.id)

        # Remove initial message
        if config.user_message_delete_delay >= 0:
            await ctx.message.delete(delay=config.user_message_delete_delay)


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
