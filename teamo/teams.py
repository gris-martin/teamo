from typing import List
from math import floor
import random
import pathlib

import discord

from teamo.models import Member, Entry
from teamo.utils import get_date_string

current_filepath = pathlib.Path(__file__).parent.absolute()
noun_filename = f"{current_filepath}/nouns.list"
adjectives_filename = f"{current_filepath}/adjectives.list"


def generate_name_list(filename: str) -> List[str]:
    with open(filename) as f:
        lines = [line.strip() for line in f.readlines()
                 if not line.startswith("#")]
        return lines


def generate_name():
    nouns = generate_name_list(noun_filename)
    adjectives = generate_name_list(adjectives_filename)
    noun: str = random.choice(nouns)
    adjective: str = random.choice(adjectives)
    return f"{adjective.capitalize()} {noun.capitalize()}"


class Team:
    def __init__(self, member: Member = None):
        self.members: List[Member] = list()
        self.name: str = generate_name()
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
            member_string += f"<@{member.user_id}> ({member.num_players})\n"
        return member_string[:-1]


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
            tmp_teams.sort(key=lambda e: e.get_num_players())
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


def create_finish_embed(entry: Entry):
    embed = discord.Embed(
        title=f"**{entry.game} @ {get_date_string(entry.start_date, False)}**"
    )

    if len(entry.members) == 0:
        embed.add_field(name="Player list empty",
                        value="No one registered for the game :c Maybe next time!")
    else:
        teams = create_teams(entry)
        for team in teams:
            embed.add_field(
                name=f"{team.name} ({team.get_num_players()} players)",
                value=team.get_member_string(),
                inline=False
            )
    return embed
