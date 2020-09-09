import asyncio
from datetime import datetime
from dataclasses import dataclass, astuple
import uuid
from typing import List
from sqlite3 import PARSE_DECLTYPES

import aiosqlite

from teamo import models

class Database:
    def __init__(self, db_name: str):
        self.db_name: str = db_name

    async def init(self):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute('''CREATE TABLE IF NOT EXISTS entries (
                entry_id integer primary key,
                channel_id integer,
                server_id integer,
                game text,
                start_date timestamp,
                max_players integer
                )''')

            await db.execute('''CREATE TABLE IF NOT EXISTS members (
                entry_id integer,
                member_id integer,
                num_players integer,
                primary key (member_id, entry_id)
                foreign key (entry_id) references entries (entry_id)
                )''')

            await db.execute('''CREATE TABLE IF NOT EXISTS settings (
                guild_id integer primary key,
                use_channel_id integer,
                waiting_channel_id integer,
                end_channel_id integer,
                delete_use_delay integer,
                delete_end_delay integer,
                cancel_delay integer
                )''')

    ############## Entry methods ##############
    async def get_entry(self, message_id: int) -> models.Entry:
        async with aiosqlite.connect(self.db_name, detect_types=PARSE_DECLTYPES) as db:
            entry_cursor = await db.execute(
                "SELECT * FROM entries WHERE entry_id=?", (message_id,)
            )
            entry_row = await entry_cursor.fetchone()
            if entry_row is None:
                return None
            entry = models.Entry(*entry_row)

            row_cursor = await db.execute(
                "SELECT member_id, num_players FROM members WHERE entry_id=?", (message_id,)
            )
            member_rows = await row_cursor.fetchall()
            for row in member_rows:
                member = models.Member(*row)
                entry.members.append(member)

            return entry

    async def insert_entry(self, entry: models.Entry):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute(
                "INSERT INTO entries VALUES (?, ?, ?, ?, ?, ?)",
                astuple(entry)[:-1]
            )

            member_tuple_list = list(map(lambda m: (entry.message_id, m.user_id, m.num_players), entry.members))
            await db.executemany(
                "INSERT INTO members VALUES (?, ?, ?)", member_tuple_list
            )

            await db.commit()

    async def get_all_entries(self) -> List[models.Entry]:
        async with aiosqlite.connect(self.db_name, detect_types=PARSE_DECLTYPES) as db:
            # Get entries
            entry_cursor = await db.execute("SELECT * FROM entries")
            entry_rows = await entry_cursor.fetchall()
            entries = dict()
            for row in entry_rows:
                entry = models.Entry(*row)
                entries[entry.message_id] = entry

            # Append members
            member_cursor = await db.execute("SELECT * FROM members")
            member_rows = await member_cursor.fetchall()
            for row in member_rows:
                member = models.Member(*row[1:])
                entries[row[0]].members.append(member)

            return list(entries.values())

    async def delete_entry(self, message_id: int):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute(
                "DELETE FROM entries WHERE entry_id=?", (message_id,)
            )
            await db.execute(
                "DELETE FROM members WHERE entry_id=?", (message_id,)
            )
            await db.commit()

    async def delete_entries(self, message_ids: List[int]):
        message_ids_tup = list(map(lambda id: (id,), message_ids))
        async with aiosqlite.connect(self.db_name) as db:
            await db.executemany(
                "DELETE FROM entries WHERE entry_id=?", message_ids_tup
            )
            await db.executemany(
                "DELETE FROM members WHERE entry_id=?", message_ids_tup
            )
            await db.commit()

    ############## Member methods ##############
    async def get_member(self, entry_id: int, member_id: int) -> models.Member:
        async with aiosqlite.connect(self.db_name, detect_types=PARSE_DECLTYPES) as db:
            cursor = await db.execute(
                "SELECT member_id, num_players FROM members WHERE entry_id=? AND member_id=?",
                (entry_id, member_id)
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            return models.Member(*row)

    async def insert_member_raw(self, db, entry_id: int, member: models.Member):
        await db.execute(
            "INSERT INTO members VALUES (?, ?, ?)",
            (
                entry_id,
                member.user_id,
                member.num_players
            )
        )
        await db.commit()

    async def insert_member(self, entry_id: int, member: models.Member):
        async with aiosqlite.connect(self.db_name) as db:
            await self.insert_member_raw(db, entry_id, member)

    async def edit_or_insert_member(self, entry_id: int, member: models.Member) -> int:
        '''Adds the Member member to the members table if it doesn't exist,
        or updates its number of players if it does.

        Returns an integer with the number of players the previous member had.
        '''
        async with aiosqlite.connect(self.db_name) as db:
            # Check if member exists in database
            member_cursor = await db.execute(
                '''SELECT * FROM members
                WHERE entry_id=?
                AND member_id=?''',
                (
                    entry_id,
                    member.user_id
                )
            )
            member_row = await member_cursor.fetchone()

            # Create member if it doesn't exist,
            # update number of players if it does exist
            if member_row is None:
                await self.insert_member_raw(db, entry_id, member)
                return None

            await db.execute(
                '''
                UPDATE members
                SET num_players=?
                WHERE entry_id=?
                AND member_id=?
                ''',
                (
                    member.num_players,
                    entry_id,
                    member.user_id
                )
            )
            await db.commit()
            return member_row[2]

    async def delete_member(self, entry_id: int, member_id: int):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute(
                "DELETE FROM members WHERE entry_id=? AND member_id=?",
                (entry_id, member_id)
            )
            await db.commit()

    ############## Settings methods ##############
    async def insert_settings(self, guild_id: int, settings: models.Settings):
        async with aiosqlite.connect(self.db_name) as db:
            db_tuple = (guild_id,) + astuple(settings)
            await db.execute(
                "INSERT INTO settings VALUES (?, ?, ?, ?, ?, ?, ?)",
                db_tuple
            )
            await db.commit()

    async def edit_setting(self, guild_id: int, settings_type: models.SettingsType, setting: int):
        if (settings_type == models.SettingsType.USE_CHANNEL):
            db_key = "use_channel_id"
        elif (settings_type == models.SettingsType.WAITING_CHANNEL):
            db_key = "waiting_channel_id"
        elif (settings_type == models.SettingsType.END_CHANNEL):
            db_key = "end_channel_id"
        elif (settings_type == models.SettingsType.DELETE_USE_DELAY):
            db_key = "delete_use_delay"
        elif (settings_type == models.SettingsType.DELETE_END_DELAY):
            db_key = "delete_end_delay"
        elif (settings_type == models.SettingsType.CANCEL_DELAY):
            db_key = "cancel_delay"
        else:
            raise Exception(f"Cannot edit guild setting for guild {guild_id}, unknown setting: {settings_type}.")

        async with aiosqlite.connect(self.db_name) as db:
            await db.execute(
                f'''
                    UPDATE settings
                    SET
                        {db_key} = ?
                    WHERE guild_id=?
                ''',
                (
                    setting,
                    guild_id
                )
            )
            await db.commit()

    async def get_settings(self, guild_id: int) -> models.Settings:
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute(
                '''
                    SELECT
                        use_channel_id,
                        waiting_channel_id,
                        end_channel_id,
                        delete_use_delay,
                        delete_end_delay,
                        cancel_delay
                    FROM settings
                    WHERE guild_id=?
                ''',
                (guild_id,)
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            return models.Settings(*row)


async def main():
    db = Database(f'{uuid.uuid4()}.db')
    print(f"Created db: {db.db_name}")
    await db.init()
    entry1 = models.Entry(1, 0, 0, "Martin spel", datetime.now(), 5)
    entry2 = models.Entry(2, 0, 0, "Martin spel", datetime.now(), 5)

    await db.insert_entry(entry1)
    await db.insert_entry(entry2)

    member1 = models.Member(1, 2)
    member2 = models.Member(2, 3)
    member3 = models.Member(1, 1)

    await db.insert_member(entry1.message_id, member1)
    await db.insert_member(entry1.message_id, member2)
    await db.insert_member(entry2.message_id, member3)

    entry_get = await db.get_entry(entry1.message_id)
    entries = await db.get_all_entries()
    print(len(entries))
    print(entry_get)

    await db.delete_entry(entry1.message_id)
    entry_get = await db.get_entry(entry1.message_id)
    entries = await db.get_all_entries()
    print(len(entries))
    print(entry_get)

if __name__ == "__main__":
    asyncio.run(main())
