from datetime import datetime, timedelta
from typing import List
from math import floor

import discord
from models import Member, Entry
import config


def get_date_string(date: datetime) -> str:
    if date.date() == datetime.today().date():
        return "today " + date.strftime("%H:%M:%S")
    elif date.date() == datetime.today().date() + timedelta(days=1):
        return "tomorrow " + date.strftime("%H:%M:%S")
    else:
        return date.strftime("%Y-%m-%d %H:%M:%S")


def get_timedelta_string(td: timedelta) -> str:
    tot_secs = floor(td.total_seconds())
    if tot_secs < 60:
        return f"<1min"

    mins = floor(tot_secs / 60)
    if tot_secs < 60 * 60:
        return f"{mins}min"

    hours = floor(mins / 60)
    mins -= hours * 60
    if (hours < 24):
        return f"{hours}h {mins}min"

    days = floor(hours/24)
    hours -= days * 24
    return f"{days}days {hours}h {mins}min"


def create_embed(entry: Entry, is_cancelling: bool = False) -> discord.Embed:
    date_string = get_date_string(entry.start_date)
    embed = discord.Embed(
        title="Time for **{}**!!".format(entry.game),
        description=f"**Start: {date_string}** - To subscribe, select the #️⃣ reaction below with the number of players in your group. To cancel the event, select the {cancel_emoji} reaction."
    )
    embed.color = discord.Color.purple()
    tl: timedelta = entry.start_date - datetime.now()
    embed.add_field(name="Time left", value=get_timedelta_string(tl))
    embed.add_field(name="Players per team", value=entry.max_players)

    def get_member_string():
        if len(entry.members) > 0:
            member_string = ""
            for member in entry.members:
                member_string += f"{member.discord_user_name} (**{member.num_players}**), "
                return member_string[0:-2]
        else:
            return "No one has registered yet"

    embed.add_field(name="Registered", value=get_member_string())

    if is_cancelling:
        embed.add_field(
            name="MESSAGE WILL BE REMOVED",
            value=f"MESSAGE WILL BE REMOVED IN {config.cancel_timeout} SECONDS. PRESS {cancel_emoji} AGAIN TO ABORT.",
            inline=False
        )

    footer_text = ""
    if entry.discord_message_id is not None:
        footer_text += f"ID: {entry.discord_message_id}\n"
    footer_text += f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (updated every {config.update_interval} seconds)"
    embed.set_footer(text=footer_text)

    return embed


number_emojis = [
    "1️⃣",
    "2️⃣",
    "3️⃣",
    "4️⃣",
    "5️⃣",
    "6️⃣",
    "7️⃣",
    "8️⃣",
    "9️⃣",
    "🔟"]

cancel_emoji = "❌"


async def send_and_print(channel: discord.TextChannel, message):
    print(message)
    await channel.send(message)
