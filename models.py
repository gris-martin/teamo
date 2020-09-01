from typing import List, NamedTuple
from datetime import datetime
from dataclasses import dataclass, field
import asyncio

import discord

class Member(NamedTuple):
    discord_user_id: int
    num_players: int


class Entry:
    def __init__(
        self,
        message_id: int = None,
        channel_id: int = None,
        server_id: int = None,
        game: str = None,
        start_date=None,
        max_players: int = None,
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


@dataclass
class RuntimeEntry:
    '''
    Helper class to cache some things so we don't have to make as many
    calls to the Discord API.
    '''
    message: discord.Message = None
    lock: asyncio.Lock = None
    cancel_task: asyncio.Task = None

    @classmethod
    async def from_dbentry(cls, dbentry: Entry, client: discord.Client):
        channel: discord.TextChannel = client.get_channel(dbentry.discord_channel_id)
        message = await channel.fetch_message(dbentry.discord_message_id)
        lock = asyncio.Lock()
        cancel_task = None
        return cls(message, lock, cancel_task)

    async def sync_message(self):
        self.message = await self.message.channel.fetch_message(self.message.id)
