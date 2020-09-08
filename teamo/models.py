from typing import List
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum, auto


@dataclass
class Member:
    user_id: int
    num_players: int


@dataclass
class Entry:
    message_id: int = None
    channel_id: int = None
    server_id: int = None
    game: str = None
    start_date: datetime = None
    max_players: int = None
    members: List[Member] = field(default_factory=list)


class SettingsType(Enum):
    USE = auto()
    WAITING = auto()
    END = auto()
    DELETE = auto()

    @classmethod
    def from_string(cls, v: str):
        if v == 'use_channel': return cls.USE
        elif v == 'waiting_channel': return cls.WAITING
        elif v == 'end_channel': return cls.END
        elif v == 'delete_after': return cls.DELETE
        else: raise Exception(f"Cannot convert string '{v}' to SettingsType enum.")



@dataclass
class Settings:
    use_channel_id: int  # Which channel can Teamo be used from? None -> Every channel
    waiting_channel_id: int  # Which channel should Teamo post waiting messages? None -> Same as the channel as the command was posted
    end_channel_id: int  # Which channel should Teamo post ended messages? None -> Same as the channel as the command was posted
    delete_after: int  # When should end messages be deleted? < 0 -> Message will never be deleted
