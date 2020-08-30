from typing import List, NamedTuple
from datetime import datetime
import discord
from dataclasses import dataclass, field


class Member(NamedTuple):
    discord_user_id: int
    discord_user_name: str
    num_players: int


class Entry:
    def __init__(
        self,
        message_id: int,
        channel_id: int,
        server_id: int,
        game: str,
        start_date,
        max_players: int,
        members=None
    ):
        self.discord_message_id: int = message_id
        self.discord_channel_id: int = channel_id
        self.discord_server_id: int = server_id
        self.game: str = game
        if type(start_date) == datetime:
            self.start_date: datetime = start_date
        elif type(start_date) == str:
            self.start_date: datetime = datetime.fromisoformat(start_date)
        else:
            raise Exception(
                f"Invalid type of start_date attribute: {type(start_date)} (value: {start_date})")
        self.max_players: int = max_players
        if type(members) == list:
            self.members = members
        else:
            self.members = list()
