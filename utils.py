from datetime import datetime, timedelta
from typing import List
from math import floor

import discord
from models import Member, Entry
import config


def get_date_string(date: datetime, show_date: bool = True) -> str:
    if not show_date:
        return date.strftime("%H:%M:%S")

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
    footer_text += f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    if config.update_interval > 0:
        footer_text += f" (updated every {config.update_interval} seconds)"
    embed.set_footer(text=footer_text)

    return embed


class Team:
    def __init__(self, member: Member = None):
        self.members: List[Member] = list()
        self.name: str = "??"
        if member is not None:
            self.members.append(member)

    def copy(self):
        new_team = Team()
        for member in self.members:
            new_team.members.append(member)
        return new_team

    def get_num_players(self) -> int:
        num_players = 0
        for member in self.members:
            num_players += member.num_players
        return num_players

    def get_member_string(self) -> str:
        member_string = ""
        for member in self.members:
            member_string += f"{member.discord_user_name} ({member.num_players})"
        return member_string


def create_teams(entry: Entry) -> List[Team]:
    members = entry.members.copy()
    num_members = len(members)
    if num_members < 1:
        return list()

    teams = list()
    for member in members:
        if member.num_players <= floor(entry.max_players / 2):
            continue
        teams.append(Team(member))

    for team in teams:
        members.remove(team.members[0])

    # Bin packing problem
    # 1. Try to place all remaining members in one of the teams already created
    #      1.1 Add the highest member to the team with lowest number of members
    # 2. If there are not enough teams, create a new team with the user with the highest number of members
    # 3. Repeat 1-2 until no members left
    while True:
        tmp_teams = list()
        for team in teams:
            tmp_teams.append(team.copy())
        for member in members:
            tmp_teams.sort(key=lambda e: e.num_players)
            for team in tmp_teams:
                if (team.get_num_players() + member.num_players) > entry.max_players:
                    continue
                else:
                    team.members.append(member)
                    break

        total_num_members = 0
        for team in tmp_teams:
            total_num_members += len(team.members)
        if total_num_members == num_members:
            teams = tmp_teams
            break
        else:
            new_team = Team(members.pop(0))
            teams.push(new_team)

    return teams


async def create_finish_embed(channel: discord.TextChannel, entry: Entry):
    embed = discord.Embed(
        title=f"**{entry.game} @ {get_date_string(entry.start_date, False)}**"
    )

    teams = create_teams(entry)
    for team in teams:
        embed.add_field(
            name=f"{team.name} ({team.get_num_players()} players)",
            value=team.get_member_string()
        )

    await channel.send(embed=embed)

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
