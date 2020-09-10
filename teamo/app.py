import re
from dateparser.search import search_dates
from datetime import datetime, timedelta
from typing import Dict
import asyncio
import traceback
from pathlib import Path
import os
import sys
import argparse
import logging
import dataclasses

# Third party imports
import discord
from discord.ext import commands

# Internal imports
from teamo import models, utils, database, teamcreation, help


class Teamo(commands.Cog):
    def __init__(self, bot: commands.Bot, database_name):
        self.bot = bot
        Path("db").mkdir(exist_ok=True)
        self.db = database.Database(database_name)
        asyncio.run(self.db.init())
        self.cached_messages: Dict[int, discord.Message] = dict()
        self.locks: Dict[int, asyncio.Lock] = dict()
        self.cancel_tasks: Dict[int, asyncio.Task] = dict()
        self.startup_done: asyncio.Event
        self.bot.help_command = help.TeamoHelpCommand(self.db)

    async def delete_entry(self, message_id: int):
        async with self.locks[message_id]:
            # Delete message from discord
            await self.cached_messages[message_id].delete()
            self.cached_messages[message_id] = None

            # Delete message from db
            await self.db.delete_entry(message_id)

    async def cancel_after(self, message_id: int):
        entry = await self.db.get_entry(message_id)
        cancel_delay = await self.db.get_setting(entry.server_id, models.SettingsType.CANCEL_DELAY)
        try:
            await asyncio.sleep(cancel_delay)
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
            cancel_delay = await self.db.get_setting(entry.server_id, models.SettingsType.CANCEL_DELAY)
            await message.edit(embed=utils.create_embed(entry, cancel_delay, is_cancelling))
        except discord.NotFound:
            logging.warning(f"Attempted to update a message (ID: {entry.message_id}) that has already been deleted. Deleting message from database.")
            await self.db.delete_entry(entry.message_id)

    async def update_timer(self):
        while True:
            try:
                entries = await self.db.get_all_entries()
                for entry in entries:
                    await self.update_message(entry)
            except Exception:
                traceback.print_exc()
            await asyncio.sleep(utils.get_update_interval())

    async def finish_timer(self):
        while True:
            entries = await self.db.get_all_entries()
            for entry in entries:
                if entry.start_date > datetime.now():
                    continue
                settings = await self.db.get_settings(entry.server_id)
                channel_id = entry.channel_id if settings.end_channel == None else settings.end_channel
                channel = self.bot.get_channel(channel_id)
                embed = teamcreation.create_finish_embed(entry)
                if settings.delete_end_delay < 0:
                    await channel.send(embed=embed)
                else:
                    await channel.send(embed=embed, delete_after=settings.delete_end_delay)
                await self.delete_entry(entry.message_id)
            await asyncio.sleep(utils.get_check_interval())

    async def sync_message(self, message_id: int):
        old_message = self.cached_messages[message_id]
        channel = old_message.channel
        self.cached_messages[message_id] = await channel.fetch_message(message_id)

    async def send_and_log(self, channel: discord.TextChannel, message: str):
        logging.info(f"Sent message to Discord: {message}")
        delete_after = await self.db.get_setting(channel.guild.id, models.SettingsType.DELETE_GENERAL_DELAY)
        if delete_after < 0:
            await channel.send(message)
        else:
            await channel.send(message, delete_after=delete_after)

    async def remove_user_message(self, message: discord.Message):
        delay = await self.db.get_setting(message.guild.id, models.SettingsType.DELETE_USE_DELAY)
        if delay < 0:
            return
        await message.delete(delay=delay)

    @commands.Cog.listener()
    async def on_connect(self):
        self.startup_done = asyncio.Event()

    @commands.Cog.listener()
    async def on_ready(self):
        # Make sure all messages in database exists in a channel
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
                logging.warning(
                    f"Discord message for database entry with message id {entry.message_id} does not exist. Removing entry from database.")
                deleted_ids.append(entry.message_id)

        await self.db.delete_entries(deleted_ids)

        # Create settings entries for servers that don't already have an entry
        for guild in self.bot.guilds:
            settings = await self.db.get_settings(guild.id)
            if settings == None:
                await self.db.insert_settings(guild.id, models.Settings())

        # Create tasks for updating messages and checking whether a message is finished
        if utils.get_update_interval() > 0:
            asyncio.create_task(self.update_timer())
        asyncio.create_task(self.finish_timer())
        self.startup_done.set()
        logging.info("Teamo is ready!")

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
            previous_num_players = await self.db.edit_or_insert_member(message_id, member)

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

        # If number emoji: Remove member, update message
        async with self.locks[message_id]:
            user_id = payload.user_id
            db_member = await self.db.get_member(message_id, user_id)
            num_players = utils.number_emojis.index(str(emoji)) + 1
            if db_member.num_players != num_players:
                return
            await self.db.delete_member(message_id, user_id)
            await self.update_message(message_id)
            await self.sync_message(message_id)

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.UserInputError):
            await self.send_and_log(ctx.channel, f"Unknown arguments sent to command \"{ctx.command}\". Try `@{self.bot.user.display_name} help {ctx.command}` for information about using the command.")
        elif isinstance(error, commands.CommandNotFound):
            await self.send_and_log(ctx.channel, f"Unknown command: \"{ctx.invoked_with}\". Try `@{self.bot.user.display_name} help` to get a list of available commands.")
        else:
            await self.send_and_log(ctx.channel, f"Encountered an error with command {ctx.command}: {error}.")
            logging.error(f"Encountered an error with command {ctx.command}", exc_info=error)
        await self.remove_user_message(ctx.message)

    @commands.Cog.listener()
    async def on_command_completion(self, ctx: commands.Context):
        await self.remove_user_message(ctx.message)

    ############## Teamo commands ##############
    @commands.command(usage="<number of players> <time> <game>")
    async def create(self, ctx: commands.Context, *, arg: str):
        '''
        Create a new Teamo message.
        Arguments:
            <number of players> The number of players per team.
            <time> The time when the game should start, of the form hh:mm.
            <game> The game to play (only used for displaying the game name)

        Examples:
            @Teamo 5 18:30 League of Legends
            @Teamo 9 19:12 My Fun Game
        '''
        await self.startup_done.wait()

        settings = await self.db.get_settings(ctx.guild.id)
        teamo_use_channel = ctx.channel if settings.use_channel == None else self.bot.get_channel(settings.use_channel)
        if teamo_use_channel != ctx.channel:
            self.send_and_log(ctx.channel, f"Teamo commands can only be used in {teamo_use_channel.mention}. Try again there :)")

        # Parse arguments
        # TODO: Better date parsing
        args = re.match(r"^(\d+) (\d{1,2}:\d{2}) (.+)", arg)
        if (args is None):
            # TODO: Better error message
            await self.send_and_log(ctx.channel, "Invalid arguments to create command: {}".format(arg))
            return

        #   - Number of players
        max_players = int(args.group(1))
        n_guild_members = len(ctx.guild.members)
        if max_players < 2:
            await self.send_and_log(ctx.channel, "Number of players must be greater than 2.")
        if max_players > n_guild_members:
            await self.send_and_log(ctx.channel, "Number of players cannot be more than the number of members in the server, which is {}.".format(n_guild_members))
            return

        #   - Date
        date_str = args.group(2)
        date_results = search_dates(date_str)
        if date_results is None or len(date_results) == 0:
            await self.send_and_log(ctx.channel, "Invalid date: {}".format(date_str))
            return

        date = date_results[0][1]
        if date < datetime.now():
            date += timedelta(1)

        #   - Game
        game = args.group(3)
        max_game_chars = 30
        if len(game) > max_game_chars:
            await self.send_and_log(ctx.channel, "Game name too long, maximum length of game name is {} characters. Try again!".format(max_game_chars))
            return

        # Create message and send to Discord
        entry = models.Entry(
            game=game,
            start_date=date,
            max_players=max_players
        )
        embed = utils.create_embed(entry)
        teamo_post_channel = ctx.channel if settings.waiting_channel == None else self.bot.get_channel(settings.waiting_channel)
        message: discord.Message = await teamo_post_channel.send(embed=embed)
        self.cached_messages[message.id] = message

        # Create database and runtime entries
        entry.message_id = message.id
        entry.channel_id = teamo_post_channel.id
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

        self.cached_messages[message.id] = await teamo_post_channel.fetch_message(message.id)

        # Remove initial message
        delete_delay = await self.db.get_setting(ctx.guild.id, models.SettingsType.DELETE_GENERAL_DELAY)
        if delete_delay >= 0:
            await ctx.message.delete(delay=delete_delay)

    ############## Server settings commands ##############
    @commands.group()
    async def settings(self, ctx: commands.Context):
        '''
        Get or set server-specific settings.
        '''
        if ctx.author.bot:
            return
        if ctx.invoked_subcommand is None:
            await ctx.send(f"Unknown serversetting command \"{ctx.subcommand_passed}\". Try `@{self.bot.user.display_name} help serversetting` to get a list of available commands.")

    @settings.command()
    async def get(self, ctx: commands.Context, key: str):
        '''
        Get the value of a setting.
        Arguments:
            <key>: The setting to get.
        '''
        try:
            setting = models.SettingsType.from_string(key)
            v = self.db.get_setting(ctx.guild.id, setting)
            await self.send_and_log(ctx.channel, f"Server setting `{key}`: `{v}`")
        except ValueError as e:
            print("hej")
            await self.send_and_log(
                ctx.channel,
                f"Tried getting unknown setting: `{key}`. Valid settings are:\n```{utils.get_settings_string()}```\nTry `@{self.bot.user.display_name} serversetting showall` for more information about available server settings."
            )

    @settings.command()
    async def showall(self, ctx: commands.Context):
        '''
        Show all settings and their values.
        '''
        settings = await self.db.get_settings(ctx.guild.id)
        settings_dict = dataclasses.asdict(settings)
        settings_str = "**Server settings:**\n```"
        for key, value in settings_dict.items():
            settings_str += f"  {key:25} {value}\n"
        settings_str = settings_str[:-2] + "```"

        await self.send_and_log(ctx.channel, settings_str)

    @settings.command()
    async def set(self, ctx: commands.Context, key: str, value: int):
        '''
        Set a setting value.
        Arguments:
            <key>: The setting to set.
            <value>: The value to assign to the setting.
        '''

        try:
            if not ctx.author.guild_permissions.administrator:
                await self.send_and_log(ctx.channel, "Only members with the Administrator permission can set Teamo server settings.")
                return
            setting = models.SettingsType.from_string(key)
            await self.db.edit_setting(ctx.guild.id, setting, value)
            await self.send_and_log(ctx.channel, f"Successfully set `{key}` to `{value}`!")
        except ValueError as e:
            await self.send_and_log(
                ctx.channel,
                f"Tried setting unknown setting: `{key}`. Valid settings are:\n```{utils.get_settings_string()}```"
            )

    ############## Other commands ##############
    @commands.command()
    async def welcome(self, ctx: commands.Context):
        '''
        Create a nice-looking message on how to use Teamo.
        '''
        embed = discord.Embed(
            title="Teamo - Usage",
            description=
                "\n[GitHub](https://github.com/hassanbot/TeamoPy)\n\n" +
                "Use Teamo to check if people want to play, and to make teams at a given time. Use the emotes of the created message to register yourself and others (for example, if you and a friend wants to play, press 2⃣). When the time specified in the original message is reached, the bot will create a new message with information on the number of teams, and the team composition.\n\n" +
                f"Use mentions ({self.bot.user.mention}) to give a command."
        )

        embed.add_field(
            name="Format",
            value=f"{self.bot.user.mention} <number of players per team> <time to start (hh:mm)> <game>",
            inline=False
        )
        embed.add_field(
            name="Examples",
            value=
                f"{self.bot.user.mention} 5 20:00 League of Legends\n" +
                f"{self.bot.user.mention} 6 14:26 OW\n",
            inline=False
        )
        await ctx.channel.send(embed=embed)



def main():
    logging.basicConfig(level=logging.INFO)

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
        logging.info(f"Connected as {bot}")

    token = os.environ["TEAMO_BOT_TOKEN"]
    if (token is None):
        logging.error("Missing bot token. Set the TEAMO_BOT_TOKEN environment variable to the bot token found on the Discord Developer Portal.")
        sys.exit(1)

    bot.run(token)

if __name__ == "__main__":
    main()
