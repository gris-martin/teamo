import discord
from discord.ext import commands
# import dateparser
import re
from dateparser.search import search_dates
from datetime import datetime, timedelta
from typing import List, Dict
import time

# Internal imports
import models
import utils
from database import Database
import asyncio
from utils import send_and_print
import config
from teams import create_finish_embed


class Teamo(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database("teamo.db")
        asyncio.run(self.db.init())
        self.locks: Dict[int, asyncio.Lock] = dict()
        self.cancel_tasks: Dict[int, asyncio.Task] = dict()

    async def delete_entry(self, message_id: int):
        async with self.locks[message_id]:
            # Delete message from discord
            entry = await self.db.get_entry(message_id)
            channel = await self.bot.fetch_channel(entry.discord_channel_id)
            message = await channel.fetch_message(entry.discord_message_id)
            await message.delete()

            # Delete message from db
            await self.db.delete_entry(message_id)

    async def cancel_after(self, message_id: int):
        try:
            await asyncio.sleep(config.cancel_timeout)
        except asyncio.CancelledError:
            return
        await self.delete_entry(message_id)

    async def update_timer(self):
        while True:
            entries = await self.db.get_all_entries()
            for entry in entries:
                await self.update_message(entry)
            await asyncio.sleep(config.update_interval)

    async def finish_timer(self):
        while True:
            entries = await self.db.get_all_entries()
            for entry in entries:
                if entry.start_date > datetime.now():
                    continue
                channel = await self.bot.fetch_channel(entry.discord_channel_id)
                await create_finish_embed(channel, entry)
                await self.delete_entry(entry.discord_message_id)
            await asyncio.sleep(config.finish_check_interval)

    @commands.Cog.listener()
    async def on_ready(self):
        entries = await self.db.get_all_entries()
        for entry in entries:
            self.locks[entry.discord_message_id] = asyncio.Lock()
        if config.update_interval > 0:
            asyncio.create_task(self.update_timer())
        asyncio.create_task(self.finish_timer())
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

        # Add a lock if it doesn't exist (e.g. if the message was created by
        # an earlier Teamo session)
        if message_id not in self.locks:
            self.locks[message_id] = asyncio.Lock()

        # If cancel emoji: Start cancel procedure
        if emoji.name == utils.cancel_emoji:
            cancel_task = asyncio.create_task(self.cancel_after(message_id))
            self.cancel_tasks[message_id] = cancel_task
            await self.update_message(message_id)
            return

        # If number emoji: Add or edit member, remove old reactions, update message
        async with self.locks[message_id]:
            num_players = utils.number_emojis.index(emoji.name) + 1
            member = models.Member(
                payload.member.id, payload.member.display_name, num_players)
            previous_num_players = await self.db.edit_or_add_member(message_id, member)

            # Do not have to remove any reactions if the user wasn't registered before
            # or if the previous entry was the same as the current one (somehow)
            if previous_num_players is None or previous_num_players == num_players:
                await self.update_message(message_id)
                return

            # Delete old reactions
            channel: discord.TextChannel = await self.bot.fetch_channel(payload.channel_id)
            message: discord.Message = await channel.fetch_message(message_id)
            previous_emoji = utils.number_emojis[previous_num_players-1]
            old_reaction = next(
                (r for r in message.reactions if r.emoji == previous_emoji), None)
            await old_reaction.remove(payload.member)

            # Update message
            await self.update_message(message_id)

    async def update_message(self, arg):
        if type(arg) is models.Entry:
            entry = arg
            message_id = entry.discord_message_id
        elif type(arg) is int:
            entry = await self.db.get_entry(arg)
            message_id = arg
        else:
            raise Exception(
                f"Unknown argument type to update_message: {type(arg)}. Value: {arg}")
        is_cancelling = True if message_id in self.cancel_tasks else False
        channel: discord.TextChannel = await self.bot.fetch_channel(entry.discord_channel_id)
        try:
            message: discord.Message = await channel.fetch_message(entry.discord_message_id)
            await message.edit(embed=utils.create_embed(entry, is_cancelling))
        except discord.NotFound:
            await send_and_print(
                channel,
                f"WARNING: Attempted to update a message (ID: {entry.discord_message_id}) that has already been deleted. Deleting message from database."
            )
            await self.db.delete_entry(entry.discord_message_id)

    @commands.command()
    async def create(self, ctx: discord.ext.commands.Context, *, arg: str):
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
        initial_entry = models.Entry(
            game=game,
            start_date=date,
            max_players=max_players
        )
        embed = utils.create_embed(initial_entry)
        message: discord.Message = await ctx.send(embed=embed)

        # Create database entry
        entry = models.Entry(
            message_id=message.id,
            channel_id=ctx.channel.id,
            server_id=ctx.guild.id,
            game=game,
            start_date=date,
            max_players=max_players
        )
        await self.db.insert_entry(entry)

        # Update message again to show ID
        # Add reactions
        self.locks[entry.discord_message_id] = asyncio.Lock()
        await self.update_message(entry)
        async with self.locks[entry.discord_message_id]:
            for i in range(min(max_players-1, 10)):
                await message.add_reaction(utils.number_emojis[i])

            await message.add_reaction(utils.cancel_emoji)

        # Remove initial message
        if config.user_message_delete_delay >= 0:
            await ctx.message.delete(delay=config.user_message_delete_delay)
