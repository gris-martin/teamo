from typing import List
from datetime import datetime, tzinfo
from dataclasses import dataclass, field
from enum import Enum, auto
from copy import copy

from dateutil import tz


@dataclass
class Member:
    user_id: int
    num_players: int


@dataclass
class Entry:
    ''' Class for storing information of a single Teamo entry.

    Instances of this class should be created with the create_with_tz class
    method, and not by the default constructor (as the latter will yield a
    non-aware datetime object)
    '''

    message_id: int = None
    channel_id: int = None
    server_id: int = None
    game: str = None
    start_date: datetime = None
    max_players: int = None
    members: List[Member] = field(default_factory=list)

    @classmethod
    def create_with_tz(cls, *args, tzinfo: tzinfo):
        d: datetime = args[4]  # start_date argument
        d = d.replace(tzinfo=tzinfo)
        return cls(*args[0:4], d, *args[5:])

    def with_naive_datetime(self):
        new_entry = copy(self)
        new_entry.start_date = new_entry.start_date.replace(tzinfo=None)
        return new_entry

class SettingsType(Enum):
    USE_CHANNEL = auto()
    WAITING_CHANNEL = auto()
    END_CHANNEL = auto()
    DELETE_GENERAL_DELAY = auto()
    DELETE_USE_DELAY = auto()
    DELETE_END_DELAY = auto()
    CANCEL_DELAY = auto()
    TIMEZONE = auto()

    @classmethod
    def from_string(cls, v: str):
        if v == 'use_channel': return cls.USE_CHANNEL
        elif v == 'waiting_channel': return cls.WAITING_CHANNEL
        elif v == 'end_channel': return cls.END_CHANNEL
        elif v == 'delete_general_delay': return cls.DELETE_GENERAL_DELAY
        elif v == 'delete_use_delay': return cls.DELETE_USE_DELAY
        elif v == 'delete_end_delay': return cls.DELETE_END_DELAY
        elif v == 'cancel_delay': return cls.CANCEL_DELAY
        elif v == 'timezone': return cls.TIMEZONE
        else: return None

    def to_string(self) -> str:
        if self == self.USE_CHANNEL: return 'use_channel'
        elif self == self.WAITING_CHANNEL: return 'waiting_channel'
        elif self == self.END_CHANNEL: return 'end_channel'
        elif self == self.DELETE_GENERAL_DELAY: return 'delete_general_delay'
        elif self == self.DELETE_USE_DELAY: return 'delete_use_delay'
        elif self == self.DELETE_END_DELAY: return 'delete_end_delay'
        elif self == self.CANCEL_DELAY: return 'cancel_delay'
        elif self == self.TIMEZONE: return 'timezone'
        else: return None

    def is_channel_id(self) -> bool:
        if self == self.USE_CHANNEL or self == self.WAITING_CHANNEL or self == self.END_CHANNEL:
            return True
        return False

@dataclass
class Settings:
    ''' Class for holding per-server settings

    Attributes:
        use_channel (int) The channel ID of the channel where Teamo messages will be accepted. None -> Every channel is allowed. Default: None
        waiting_channel (int) The channel ID of the channel where Teamo should post the "waiting" messages. None -> Same as the channel as the command was posted. Default: None
        end_channel (int) The channel ID of the channel where Teamo should post the "end" messages. None -> Same as the channel as the command was posted. Default: None
        delete_general_delay (int) Number of seconds after Teamo posts a general message (e.g. error or help message) that it will be deleted. < 0 -> Message will never be deleted. Default: 15
        delete_use_delay (int) Number of seconds after a message directed at Teamo will be deleted. < 0 -> Message will never be deleted. Default: 5
        delete_end_delay (int) Number of seconds after an "end" message has been posted that it will be deleted. < 0 -> Message will never be deleted. Default: 0
        cancel_delay (int) Number of seconds after a cancel reaction has been pressed that the message will be deleted. < 0 -> Message will be deleted immediately. Default: 15
        timezone (str) The timezone of the server, specified as a IANA timezone database name. Default: "Europe/Stockholm"
    '''
    use_channel: int = None
    waiting_channel: int = None
    end_channel: int = None
    delete_general_delay: int = 30
    delete_use_delay: int = 30
    delete_end_delay: int = 60 * 60
    cancel_delay: int = 30
    timezone: str = "Europe/Stockholm"

    def get_tzinfo(self) -> tzinfo:
        return tz.gettz(self.timezone)
