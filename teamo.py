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


class Teamo(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database("teamo.db")
        asyncio.run(self.db.init())
        self.locks: Dict[int, asyncio.Lock] = dict()

    # TODO: All of this should be executed before starting another event...
    # To replicate: Try adding many reactions at once.
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
            print("TODO: Cancelling!")
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
                return

            channel: discord.TextChannel = await self.bot.fetch_channel(payload.channel_id)
            message: discord.Message = await channel.fetch_message(message_id)
            previous_emoji = utils.number_emojis[previous_num_players-1]
            old_reaction = next(
                (r for r in message.reactions if r.emoji == previous_emoji), None)
            await old_reaction.remove(payload.member)

            # TODO: Update message
            new_entry = await self.db.get_entry(message_id)
            await self.update_message(new_entry)

    async def update_message(self, entry: models.Entry):
        channel: discord.TextChannel = await self.bot.fetch_channel(entry.discord_channel_id)
        message: discord.Message = await channel.fetch_message(entry.discord_message_id)
        await message.edit(embed=utils.create_embed(entry.game, entry.start_date, entry.max_players, entry.members))

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

        # Create message
        #   Create embed
        embed = utils.create_embed(game, date, max_players)

        #   Send embed to Discord
        message: discord.Message = await ctx.send(embed=embed)

        # Create database entry
        entry = models.Entry(message.id, ctx.channel.id,
                             ctx.guild.id, game, date, max_players)
        await self.db.insert_entry(entry)

        self.locks[entry.discord_message_id] = asyncio.Lock()
        async with self.locks[entry.discord_message_id]:
            for i in range(min(max_players-1, 10)):
                await message.add_reaction(utils.number_emojis[i])

            await message.add_reaction(utils.cancel_emoji)
