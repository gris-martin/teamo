from database import Database
from pathlib import Path
import asyncio
import argparse

parser = argparse.ArgumentParser(description='Initialize an empty database file.')
parser.add_argument(
    "path",
    type=str,
    nargs=1,
    default="db/teamo.db",
    help="specify the location of the database to use (default: db/teamo.db)"
)
args = parser.parse_args()


async def main():
    Path(args.path[0]).parent.mkdir(exist_ok=True, parents=True)
    db = Database(args.path[0])
    await db.init()

asyncio.run(main())
