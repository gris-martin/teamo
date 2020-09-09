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

    entry.message_id = 1
    entry.members.append(models.Member(0, 1))
    entry.members.append(models.Member(1, 1))
    await db.insert_entry(entry)

    db_entry = await db.get_entry(1)
    assert entry == db_entry

    db_entries = await db.get_all_entries()
    assert len(db_entries) == 2
    assert db_entries[1] == entry

@pytest.mark.asyncio
async def test_delete_member(db):
    entry = models.Entry(
        message_id = 0,
        channel_id = 0,
        server_id = 0,
        game = "Testgame",
        start_date = datetime.now(),
        max_players = 4
    )

    await db.insert_entry(entry)
    member0 = models.Member(0, 1)
    member1 = models.Member(1, 3)
    member5 = models.Member(5, 2)
    await db.insert_member(0, member0)
    await db.insert_member(0, member1)
    await db.insert_member(0, member5)

    await db.insert_entry(dataclasses.replace(entry, message_id=1))
    member4 = models.Member(4, 3)
    await db.insert_member(1, member1)
    await db.insert_member(1, member4)

    await db.delete_member(0, 1)
    db_entry0 = await db.get_entry(0)
    assert len(db_entry0.members) == 2
    assert (await db.get_member(0, 0)) == member0
    assert (await db.get_member(0, 1)) == None
    assert (await db.get_member(0, 5)) == member5

    await db.delete_member(1, 4)
    db_entry1 = await db.get_entry(1)
    assert len(db_entry1.members) == 1
    assert db_entry1.members[0] == member1

@pytest.mark.asyncio
async def test_get_member(db):
    entry = models.Entry(
        message_id = 0,
        channel_id = 0,
        server_id = 0,
        game = "Testgame",
        start_date = datetime.now(),
        max_players = 4
    )
    member1 = models.Member(1, 3)
    member3 = models.Member(3, 2)
    entry.members.append(member1)
    entry.members.append(member3)
    await db.insert_entry(entry)

    db_member1 = await db.get_member(0, 1)
    db_member3 = await db.get_member(0, 3)

    assert db_member1 == member1
    assert db_member3 == member3

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


@pytest.mark.asyncio
async def test_settings(db: Database):
    settings0 = models.Settings(
        use_channel=0,
        waiting_channel=0,
        end_channel=0
    )
    settings1 = models.Settings(
        use_channel=1,
        waiting_channel=2,
        end_channel=3,
        delete_general_delay=4,
        delete_use_delay=5,
        delete_end_delay=6,
        cancel_delay=7
    )
    await db.insert_settings(0, settings0)
    await db.insert_settings(1, settings1)

    db_settings0 = await db.get_settings(0)
    assert settings0 == db_settings0
    db_settings1 = await db.get_settings(1)
    assert settings1 == db_settings1

    await db.edit_setting(0, models.SettingsType.USE_CHANNEL, 6)
    await db.edit_setting(0, models.SettingsType.WAITING_CHANNEL, 1)
    await db.edit_setting(0, models.SettingsType.END_CHANNEL, 3)
    await db.edit_setting(0, models.SettingsType.DELETE_GENERAL_DELAY, 155)
    await db.edit_setting(0, models.SettingsType.DELETE_USE_DELAY, 2)
    await db.edit_setting(0, models.SettingsType.DELETE_END_DELAY, 7)
    await db.edit_setting(0, models.SettingsType.CANCEL_DELAY, 12)
    db_settings_edited = await db.get_settings(0)
    assert db_settings_edited.use_channel == 6
    assert db_settings_edited.waiting_channel == 1
    assert db_settings_edited.end_channel == 3
    assert db_settings_edited.delete_general_delay == 155
    assert db_settings_edited.delete_use_delay == 2
    assert db_settings_edited.delete_end_delay == 7
    assert db_settings_edited.cancel_delay == 12
