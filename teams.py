from typing import List
from math import floor

import discord

from models import Member, Entry
from utils import get_date_string


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
            teams.append(new_team)

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
