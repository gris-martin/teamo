from typing import List, NamedTuple
from datetime import datetime
from dataclasses import dataclass, field


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
