import tempfile
from datetime import datetime
import dataclasses

import pytest

from teamo.database import Database
from teamo import models

@pytest.fixture
async def db():
    with tempfile.TemporaryDirectory() as tmpdirname:
        db = Database(f"{tmpdirname}/test.db")
        await db.init()
        yield db

@pytest.mark.asyncio
async def test_insert_entry(db):
    entry = models.Entry(
        message_id = 0,
        channel_id = 0,
        server_id = 0,
        game = "Testgame",
        start_date = datetime.now(),
        max_players = 1
    )

    await db.insert_entry(entry)
    db_entry = await db.get_entry(0)
    assert entry == db_entry

    db_entries = await db.get_all_entries()
    assert len(db_entries) == 1
    assert db_entries[0] == entry

@pytest.mark.asyncio
async def test_insert_member(db):
    entry = models.Entry(
        message_id = 0,
        channel_id = 0,
        server_id = 0,
        game = "Testgame",
        start_date = datetime.now(),
        max_players = 1
    )

    await db.insert_entry(entry)

    member1 = models.Member(0, 1)
    member2 = models.Member(1, 2)

    await db.insert_member(0, member1)

    db_entry = await db.get_entry(0)
    assert len(db_entry.members) == 1
    assert db_entry.members[0] == member1

    await db.edit_or_insert_member(0, member2)
    db_entry = await db.get_entry(0)
    assert len(db_entry.members) == 2
    assert db_entry.members[1] == member2

    member1.num_players = 4
    await db.edit_or_insert_member(0, member1)
    db_entry = await db.get_entry(0)
    assert db_entry.members[0].num_players == 4

@pytest.mark.asyncio
async def test_delete_entry(db):
    entry = models.Entry(
        message_id = 0,
        channel_id = 0,
        server_id = 0,
        game = "Testgame",
        start_date = datetime.now(),
        max_players = 1
    )

    await db.insert_entry(entry)
    await db.insert_entry(dataclasses.replace(entry, message_id=1))

    db_entries = await db.get_all_entries()
    assert len(db_entries) == 2

    await db.delete_entry(0)
    db_entries = await db.get_all_entries()
    assert len(db_entries) == 1

    await db.insert_entry(dataclasses.replace(entry, message_id=0))
    await db.insert_entry(dataclasses.replace(entry, message_id=3))
    await db.insert_entry(dataclasses.replace(entry, message_id=4))
    db_entries = await db.get_all_entries()
    assert len(db_entries) == 4

    await db.delete_entries([0, 1, 4])
    db_entries = await db.get_all_entries()
    assert len(db_entries) == 1
    assert db_entries[0] == dataclasses.replace(entry, message_id=3)
