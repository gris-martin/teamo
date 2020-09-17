from dataclasses import astuple
import logging
import sys
from typing import List
from sqlite3 import PARSE_DECLTYPES

import aiosqlite
from dateutil import tz

from teamo import models

class Database:
    def __init__(self, db_name: str):
        self.db_name: str = db_name

    async def init(self):
        async with aiosqlite.connect(self.db_name, detect_types=PARSE_DECLTYPES) as db:
            logging.info(f"Using database file {self.db_name}")
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
                use_channel integer,
                waiting_channel integer,
                end_channel integer,
                delete_general_delay integer,
                delete_use_delay integer,
                delete_end_delay integer,
                cancel_delay integer,
                timezone text
                )''')

    def check_connected(func):
        async def wrapper(self, *args, db=None, **kwargs):
            has_db = True
            if db == None:
                has_db = False
                db = await aiosqlite.connect(self.db_name, detect_types=PARSE_DECLTYPES)
            try:
                return await func(self, *args, db=db, **kwargs)
            finally:
                if not has_db:
                    await db.close()

        return wrapper

    ############## Entry methods ##############
    @check_connected
    async def get_entry(self, message_id: int, db=None) -> models.Entry:
        # Get the time zone info
        server_id = await self.get_entry_server_id(message_id, db=db)
        settings = await self.get_settings(server_id, db=db)
        tzinfo = settings.get_tzinfo()

        # Get the entry from db and create the Entry object
        entry_cursor = await db.execute(
            "SELECT * FROM entries WHERE entry_id=?", (message_id,)
        )
        entry_row = await entry_cursor.fetchone()
        if entry_row is None:
            return None
        entry = models.Entry.create_with_tz(*entry_row, tzinfo=tzinfo)

        # Add members
        row_cursor = await db.execute(
            "SELECT member_id, num_players FROM members WHERE entry_id=?", (message_id,)
        )
        member_rows = await row_cursor.fetchall()
        for row in member_rows:
            member = models.Member(*row)
            entry.members.append(member)

        return entry

    @check_connected
    async def exists_entry(self, message_id: int, db=None) -> bool:
        cursor = await db.execute(
            "SELECT * FROM entries WHERE entry_id=?", (message_id,)
        )
        row = await cursor.fetchone()
        if row is None:
            return False
        return True

    @check_connected
    async def insert_entry(self, entry: models.Entry, db=None):
        await db.execute(
            "INSERT INTO entries VALUES (?, ?, ?, ?, ?, ?)",
            astuple(entry.with_naive_datetime())[:-1]
        )

        member_tuple_list = list(map(lambda m: (entry.message_id, m.user_id, m.num_players), entry.members))
        await db.executemany(
            "INSERT INTO members VALUES (?, ?, ?)", member_tuple_list
        )

        await db.commit()

    @check_connected
    async def get_all_entries(self, db=None) -> List[models.Entry]:
        entry_id_cursor = await db.execute("SELECT entry_id FROM entries")
        entry_id_rows = await entry_id_cursor.fetchall()
        entries = dict()
        for row in entry_id_rows:
            entries[row[0]] = await self.get_entry(row[0], db=db)

        return list(entries.values())

    @check_connected
    async def get_entry_server_id(self, message_id: int, db=None) -> int:
        cursor = await db.execute(
            "SELECT server_id FROM entries WHERE entry_id=?", (message_id,)
        )
        row = await cursor.fetchone()
        if row is None: return None
        return row[0]

    @check_connected
    async def delete_entry(self, message_id: int, db=None):
        await db.execute(
            "DELETE FROM entries WHERE entry_id=?", (message_id,)
        )
        await db.execute(
            "DELETE FROM members WHERE entry_id=?", (message_id,)
        )
        await db.commit()

    @check_connected
    async def delete_entries(self, message_ids: List[int], db=None):
        message_ids_tup = list(map(lambda id: (id,), message_ids))
        await db.executemany(
            "DELETE FROM entries WHERE entry_id=?", message_ids_tup
        )
        await db.executemany(
            "DELETE FROM members WHERE entry_id=?", message_ids_tup
        )
        await db.commit()

    ############## Member methods ##############
    @check_connected
    async def get_member(self, entry_id: int, member_id: int, db=None) -> models.Member:
        cursor = await db.execute(
            "SELECT member_id, num_players FROM members WHERE entry_id=? AND member_id=?",
            (entry_id, member_id)
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return models.Member(*row)

    @check_connected
    async def insert_member(self, entry_id: int, member: models.Member, db=None):
        await db.execute(
            "INSERT INTO members VALUES (?, ?, ?)",
            (
                entry_id,
                member.user_id,
                member.num_players
            )
        )
        await db.commit()

    @check_connected
    async def edit_or_insert_member(self, entry_id: int, member: models.Member, db=None) -> int:
        '''Adds the Member member to the members table if it doesn't exist,
        or updates its number of players if it does.

        Returns an integer with the number of players the previous member had.
        '''

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
            await self.insert_member(entry_id, member, db=db)
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

    @check_connected
    async def delete_member(self, entry_id: int, member_id: int, db=None):
        await db.execute(
            "DELETE FROM members WHERE entry_id=? AND member_id=?",
            (entry_id, member_id)
        )
        await db.commit()

    ############## Settings methods ##############
    @check_connected
    async def insert_settings(self, guild_id: int, settings: models.Settings, db=None):
        db_tuple = (guild_id,) + astuple(settings)
        await db.execute(
            "INSERT INTO settings VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            db_tuple
        )
        await db.commit()

    @check_connected
    async def edit_setting(self, guild_id: int, settings_type: models.SettingsType, setting: str, db=None):
        db_key = settings_type.to_string()
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

    @check_connected
    async def get_setting(self, guild_id: int, setting: models.SettingsType, db=None):
        db_key = setting.to_string()
        cursor = await db.execute(
            f'SELECT {db_key} FROM settings WHERE guild_id=?',
            (guild_id,)
        )
        row = await cursor.fetchone()
        if row is None:
            raise Exception(f"Could not get setting {setting} from guild with id {guild_id}.")
        return row[0]

    @check_connected
    async def get_settings(self, guild_id: int, db=None) -> models.Settings:
        cursor = await db.execute(
            '''
                SELECT
                    use_channel,
                    waiting_channel,
                    end_channel,
                    delete_general_delay,
                    delete_use_delay,
                    delete_end_delay,
                    cancel_delay,
                    timezone
                FROM settings
                WHERE guild_id=?
            ''',
            (guild_id,)
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return models.Settings(*row)
