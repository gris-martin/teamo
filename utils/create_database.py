from pathlib import Path
import asyncio
import argparse
import aiosqlite

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

async def main():
    parser = argparse.ArgumentParser(description='Initialize an empty database file.')
    parser.add_argument(
        "path",
        type=str,
        nargs=1,
        default="db/teamo.db",
        help="specify the location of the database to use (default: db/teamo.db)"
    )
    args = parser.parse_args()

    Path(args.path[0]).parent.mkdir(exist_ok=True, parents=True)
    db = Database(args.path[0])
    await db.init()

if __name__ == "__main__":
    asyncio.run(main())
