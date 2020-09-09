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
    USE_CHANNEL = auto()
    WAITING_CHANNEL = auto()
    END_CHANNEL = auto()
    DELETE_USE_DELAY = auto()
    DELETE_END_DELAY = auto()
    CANCEL_DELAY = auto()

    @classmethod
    def from_string(cls, v: str):
        if v == 'use_channel': return cls.USE_CHANNEL
        elif v == 'waiting_channel': return cls.WAITING_CHANNEL
        elif v == 'end_channel': return cls.END_CHANNEL
        elif v == 'delete_use_delay': return cls.DELETE_USE_DELAY
        elif v == 'delete_end_delay': return cls.DELETE_END_DELAY
        elif v == 'cancel_delay': return cls.CANCEL_DELAY
        else: raise Exception(f"Cannot convert string '{v}' to SettingsType enum.")


@dataclass
class Settings:
    ''' Class for holding per-server settings

    Attributes:
        use_channel_id (int) The channel ID of the channel where Teamo messages will be accepted. None -> Every channel is allowed. Default: Create a new channel named "teamo" and only allow messages there.
        waiting_channel_id (int) The channel ID of the channel where Teamo should post the "waiting" messages. None -> Same as the channel as the command was posted. Default: Create a new channel named "teamo" and post messages there.
        end_channel_id (int) The channel ID of the channel where Teamo should post the "end" messages. None -> Same as the channel as the command was posted. Default: Create a new channel named "teamo" and post messages there.
        delete_use_delay (int) Number of seconds after a message directed at Teamo will be deleted. < 0 -> Message will never be deleted. Default: 5
        delete_end_delay (int) Number of seconds after an "end" message has been posted that it will be deleted. < 0 -> Message will never be deleted. Default: -1
        cancel_delay (int) Number of seconds after a cancel reaction has been pressed that the message will be deleted. < 0 -> Message will be deleted immediately. Defualt: 15
    '''
    use_channel_id: int
    waiting_channel_id: int
    end_channel_id: int
    delete_use_delay: int = 5
    delete_end_delay: int = -1
    cancel_delay: int = 15
