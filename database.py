import asyncio
import aiosqlite
import discord
from datetime import datetime
from dataclasses import dataclass
import uuid

import models

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
                member_name text,
                num_players integer,
                primary key (member_id, entry_id)
                foreign key (entry_id) references entries (entry_id)
                )''')

    async def insert_entry(self, entry: models.Entry):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute(
                "INSERT INTO entries VALUES (?, ?, ?, ?, ?, ?)",
                (
                    entry.discord_message_id,
                    entry.discord_channel_id,
                    entry.discord_server_id,
                    entry.game,
                    entry.start_date,
                    entry.max_players
                )
            )
            await db.commit()


    async def insert_member_raw(self, db, entry_id: int, member: models.Member):
        await db.execute(
            "INSERT INTO members VALUES (?, ?, ?, ?)",
            (
                entry_id,
                member.discord_user_id,
                member.discord_user_name,
                member.num_players
            )
        )
        await db.commit()

    async def insert_member(self, entry_id: int, member: models.Member):
        async with aiosqlite.connect(self.db_name) as db:
            await self.insert_member_raw(db, entry_id, member)


    async def edit_or_add_member(self, entry_id: int, member: models.Member) -> int:
        '''Adds the Member member to the members table if it doesn't exist, or
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
                    member.discord_user_id
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
                    member.discord_user_id
                )
            )
            await db.commit()
            return member_row[3]

    # async def delete_member(self, entry: models.Entry, discord_user_id: int):
    #     async with aiosqlite.connect(self.db_name) as db:
    #         await db.execute(
    #             "DELETE FROM members WHERE "
    #         )

    async def get_entry(self, message_id: int) -> models.Entry:
        async with aiosqlite.connect(self.db_name) as db:
            entry_cursor = await db.execute(
                "SELECT * FROM entries WHERE entry_id=?", (message_id,)
            )
            entry_row = await entry_cursor.fetchone()
            if entry_row is None:
                return None
            entry = models.Entry(*entry_row)

            row_cursor = await db.execute(
                "SELECT * FROM members WHERE entry_id=?", (message_id,)
            )
            member_rows = await row_cursor.fetchall()
            for row in member_rows:
                member = models.Member(*row[1:])
                entry.members.append(member)

            return entry


async def main():
    # db = Database(':memory:')
    db = Database(f'{uuid.uuid4()}.db')
    print(f"Created db: {db.db_name}")
    await db.init()
    # await db.init()
    entry1 = models.Entry(1, 0, 0, "Martin spel", datetime.now(), 5)
    entry2 = models.Entry(2, 0, 0, "Martin spel", datetime.now(), 5)
    # entry3 = models.Entry("Martin spel", datetime.now(), 5, 3, 0)
    # entry4 = models.Entry("Martin spel", datetime.now(), 5, 4, 0)

    await db.insert_entry(entry1)
    await db.insert_entry(entry2)
    # await db.insert_entry(entry3)
    # await db.insert_entry(entry4)

    member1 = models.Member(1, "Martin 1", 2)
    member2 = models.Member(2, "Martin 2", 3)
    member3 = models.Member(1, "Martin 1", 1)

    await db.insert_member(entry1.discord_message_id, member1)
    await db.insert_member(entry1.discord_message_id, member2)
    await db.insert_member(entry2.discord_message_id, member3)

    entry_get = await db.get_entry(entry1.discord_message_id)
    print(entry_get)
    # member1 = models.Member(1, "Martin 1", 2)

if __name__ == "__main__":
    asyncio.run(main())



# class Member:
#     id: int
#     discord_user_id: int
#     num_players: int
#     post_id: int

# class DiscordMessage:
#     channel_id: int
#     message_id: int

# class Entry:
#     id: int
#     message: DiscordMessage
#     # message: discord.Message
#     game: str
#     end_date: datetime.datetime
#     max_players: int

#     def __init__(self):
#         print("hej")





# async def main():
#     async with aiosqlite.connect("martin.db") as db:
#         async with db.cursor() as cursor:
#             await cursor.execute('''CREATE TABLE IF NOT EXISTS stocks (
#                 date text,
#                 trans text,
#                 symbol text,
#                 qty real,
#                 price real)''')
#             await cursor.execute("INSERT INTO stocks VALUES ('2006-01-05','BUY','RHAT',100,35.14)")
#             # await cursor.execute('''CREATE TABLE martin (
#             #     id INTEGER PRIMARY KEY
#             #     name TEXT
#             #     number REAL
#             #     )''')

#             # await cursor.execute("INSERT INTO martin VALUES (1, 'mm', 2.14)")
#         await db.commit()

# asyncio.run(main())
