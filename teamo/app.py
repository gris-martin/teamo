import re
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
from dateutil import parser, tz
from dateutil.parser._parser import ParserError
from dotenv import load_dotenv

# Internal imports
from teamo import models, utils, database, teamcreation, help


class Teamo(commands.Cog):
    def __init__(self, bot: commands.Bot, database_name):
        self.bot = bot
        Path("db").mkdir(exist_ok=True)
        self.db = database.Database(database_name)
        self.cached_messages: Dict[int, discord.Message] = dict()
        self.locks: Dict[int, asyncio.Lock] = dict()
        self.cancel_tasks: Dict[int, asyncio.Task] = dict()
        self.startup_done: asyncio.Event
        self.bot.help_command = help.TeamoHelpCommand(self.db)

    async def delete_entry(self, message_id: int):
        async with self.locks[message_id]:
            # Delete message from db
            await self.db.delete_entry(message_id)

            # Delete message from discord
            await self.cached_messages[message_id].delete()
            self.cached_messages[message_id] = None

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
                logging.info(f"Teamo message {entry.message_id} is finished. Creating end message.")
                settings = await self.db.get_settings(entry.server_id)
                channel_id = entry.channel_id if settings.end_channel == None else settings.end_channel
                channel = self.bot.get_channel(channel_id)
                embed = teamcreation.create_finish_embed(entry)
                if settings.delete_end_delay < 0:
                    end_message = await channel.send(embed=embed)
                else:
                    end_message = await channel.send(embed=embed, delete_after=settings.delete_end_delay)
                logging.info(f"End message {end_message.id} created in channel {channel_id} ({channel.name}). It will be removed in {settings.delete_end_delay} seconds.")
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

    ############## Discord events ##############
    @commands.Cog.listener()
    async def on_connect(self):
        await self.db.init()
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
                tzinfo = utils.get_tzname_from_region(guild.region)
                await self.db.insert_settings(guild.id, models.Settings(timezone=tzinfo))

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
        if str(emoji) == utils.cancel_emoji:
            logging.info(f"Received cancel emoji on {message_id}")
            cancel_task = asyncio.create_task(self.cancel_after(message_id))
            self.cancel_tasks[message_id] = cancel_task
            await self.update_message(message_id)
            await self.sync_message(message_id)
            return

        # If number emoji: Add or edit member, remove old reactions, update message
        async with self.locks[message_id]:
            logging.info(f"Received number emoji {str(emoji)}  on {message_id} from user {payload.member.id} ({payload.member.display_name}")
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
        if str(emoji) == utils.cancel_emoji:
            logging.info(f"Cancel emoji removed on message {message_id}")
            cancel_task = self.cancel_tasks[message_id]
            if cancel_task is None or cancel_task.done():
                return
            cancel_task.cancel()
            self.cancel_tasks[message_id] = None
            await self.update_message(db_entry)

        # If number emoji: Remove member, update message
        async with self.locks[message_id]:
            user_id = payload.user_id
            logging.info(f"Number emoji {str(emoji)}  removed on message {message_id} by user {user_id}")
            db_member = await self.db.get_member(message_id, user_id)
            num_players = utils.number_emojis.index(str(emoji)) + 1
            if db_member.num_players != num_players:
                return
            await self.db.delete_member(message_id, user_id)
            await self.update_message(message_id)
            await self.sync_message(message_id)

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent):
        message_id = payload.message_id
        entry_exists = await self.db.exists_entry(message_id)
        if entry_exists:
            logging.info(f"Teamo message {message_id} was deleted by a user. Removing database entry.")
            await self.db.delete_entry(message_id)

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

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        settings = await self.db.get_settings(guild.id)
        if settings == None:
            tzinfo = utils.get_tzname_from_region(guild.region)
            await self.db.insert_settings(guild.id, timezone=tzinfo)
        logging.info(f"Joined guild {guild.id} ({guild.name})")

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
            create 5 18:30 League of Legends
            create 9 19.12 My Fun Game
        '''
        await self.startup_done.wait()
        logging.info(f"Teamo create command received in channel {ctx.channel.id} ({ctx.channel.name}) by user {ctx.author.id} ({ctx.author.name}) with args {arg}")
        settings = await self.db.get_settings(ctx.guild.id)
        teamo_use_channel = ctx.channel if settings.use_channel == None else self.bot.get_channel(settings.use_channel)
        if teamo_use_channel != ctx.channel:
            await self.send_and_log(ctx.channel, f"Teamo commands can only be used in {teamo_use_channel.mention}. Try again there :)")
            return

        # Parse arguments
        # TODO: Better date parsing
        args = re.match(r"^(\d+) (\d{1,2}[:\.]\d{2}) (.+)", arg)
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
        date_str = date_str.replace('\.', ':')
        # date_results = search_dates(date_str)
        # if date_results is None or len(date_results) == 0:
        #     await self.send_and_log(ctx.channel, "Invalid date/time: {}".format(date_str))
        #     return

        # date: datetime = date_results[0][1]
        currenttz=settings.get_tzinfo()
        try:
            date = parser.parse(date_str)
        except ParserError:
            await self.send_and_log(ctx.channel, f"Failed to parse date argument {args.group(2)}")
            return
        date = date.replace(tzinfo=currenttz)
        datediff = date - datetime.now(tz=currenttz)
        if datediff.total_seconds() < 0:
            if datediff + timedelta(days=1) > timedelta():
                date += timedelta(days=1)
            else:
                await self.send_and_log(ctx.channel, "Invalid date/time: {}".format(date_str))
                return

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
        logging.info(f"Teamo message {message.id} created in channel {teamo_post_channel.id} ({teamo_post_channel.name}) by {ctx.author.id} ({ctx.author.name}).")

    ############## Server settings commands ##############
    @commands.group()
    async def settings(self, ctx: commands.Context):
        '''
        Get or set server-specific settings.
        '''
        if ctx.author.bot:
            return
        if ctx.invoked_subcommand is None:
            await ctx.send(f"Unknown settings command \"{ctx.subcommand_passed}\". Try `@{self.bot.user.display_name} help settings` to get a list of available commands.")

    @settings.command()
    async def get(self, ctx: commands.Context, key: str):
        '''
        Get the value of a setting.
        Arguments:
            <key>: The setting to get.
        '''
        setting = models.SettingsType.from_string(key)
        if setting is None:
            await self.send_and_log(ctx.channel, f"Cannot get value of unknown setting: \"{key}\". Valid settings are:\n ```{utils.get_settings_string()}```")
            return
        v = await self.db.get_setting(ctx.guild.id, setting)
        if key.endswith("channel") and v is not None:
            channel_name = ctx.guild.get_channel(v)
            v = f"{v} ({channel_name})"
        await self.send_and_log(ctx.channel, f"Server setting `{key}`: `{v}`")

    @settings.command()
    async def showall(self, ctx: commands.Context):
        '''
        Show all settings and their values.
        '''
        settings = await self.db.get_settings(ctx.guild.id)
        settings_dict = dataclasses.asdict(settings)
        settings_str = "**Server settings:**\n```"
        for key, value in settings_dict.items():
            if key.endswith("channel") and value is not None:
                channel_name = ctx.guild.get_channel(value).name
                value = f"{value} ({channel_name})"

            settings_str += f"  {key:25} {value}\n"
        settings_str = settings_str[:-1] + "```"

        await self.send_and_log(ctx.channel, settings_str)

    @settings.command()
    async def set(self, ctx: commands.Context, key: str, value: str):
        '''
        Set a setting value.
        Arguments:
            <key>: The setting to set.
            <value>: The value to assign to the setting.

        Example:
            settings set delete_use_delay 40
            settings set use_channel 749638923554390096
            settings set end_channel a-channel-name
        '''
        if not ctx.author.guild_permissions.administrator:
            await self.send_and_log(ctx.channel, "Only members with the Administrator permission can set Teamo server settings.")
            return

        setting = models.SettingsType.from_string(key)
        if setting is None:
            await self.send_and_log(ctx.channel, f"Cannot set value of unknown setting: \"{key}\". Valid settings are:\n ```{utils.get_settings_string()}```")
            return

        # Make sure the time zone is a real time zone
        if setting == models.SettingsType.TIMEZONE:
            tzobj = tz.gettz(value)
            if tzobj is None:
                await self.send_and_log(ctx.channel, f"Invalid time zone: \"{value}\". See https://en.wikipedia.org/wiki/List_of_tz_database_time_zones for a list of valid time zone values.")

        # Make sure the channel exists
        if setting.is_channel_id():
            channel_found = False
            if value.isdigit():
                channel = await ctx.guild.get_channel(int(value))
                if channel is not None:
                    channel_found = True
            else:
                for channel in ctx.guild.channels:
                    if channel.name == value:
                        channel_found = True
                        value = str(channel.id)
                        break
            if not channel_found:
                await self.send_and_log(ctx.channel, f"Cannot set `{key}` to `{value}`. No channel with name or ID {value} found on this server.")
                return


        await self.db.edit_setting(ctx.guild.id, setting, value)
        await self.send_and_log(ctx.channel, f"Successfully set `{key}` to `{value}`!")

    ############## Other commands ##############
    @commands.command()
    async def welcome(self, ctx: commands.Context):
        '''
        Create a nice-looking message on how to use Teamo.
        '''
        embed = discord.Embed(
            title="Teamo - Usage",
            description=
                "Use Teamo to check if people want to play, and to make teams at a given time. Use the emotes of the created message to register yourself and others (for example, if you and a friend wants to play, press 2⃣). When the time specified in the original message is reached, the bot will create a new message with information on the number of teams, and the team composition.\n\n" +
                f"Use mentions ({self.bot.user.mention}) to give a command."
        )

        embed.add_field(
            name="Format",
            value=f"{self.bot.user.mention} create <number of players per team> <time to start (hh:mm)> <game>",
            inline=False
        )
        embed.add_field(
            name="Examples",
            value=
                f"{self.bot.user.mention} create 5 20:00 League of Legends\n" +
                f"{self.bot.user.mention} create 6 14:26 OW\n",
            inline=False
        )

        embed.add_field(
            name="Resources",
            value=
                "[GitHub](https://github.com/hassanbot/teamo)\n" +
                "[Issues](https://github.com/hassanbot/teamo/issues)\n" +
                "[Readme](https://github.com/hassanbot/teamo/blob/main/README.md)\n" +
                "[Changelog](https://github.com/hassanbot/teamo/blob/main/CHANGELOG.md)",
            inline=False
        )

        with open("VERSION") as f:
            embed.set_footer(text=f"Message generated by Teamo version {f.read()}")

        await ctx.channel.send(embed=embed)



def main():
    load_dotenv('resources/.env')
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
        await bot.change_presence(
            activity=discord.Activity(
                name=f"@{bot.user.display_name} help",
                type=discord.ActivityType.listening))
        logging.info(f"Connected as {bot} ({bot.user.display_name})")

    token = os.environ["TEAMO_BOT_TOKEN"]
    if (token is None):
        logging.error("Missing bot token. Set the TEAMO_BOT_TOKEN environment variable to the bot token found on the Discord Developer Portal.")
        sys.exit(1)

    bot.run(token)

if __name__ == "__main__":
    main()
