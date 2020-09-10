import discord
from discord.ext.commands.help import DefaultHelpCommand

from teamo import database, models

class TeamoHelpCommand(DefaultHelpCommand):
    def __init__(self, db: database.Database, **options):
        super().__init__(**options)
        self.db = db

    async def send_pages(self):
        destination: discord.TextChannel = self.get_destination()
        delete_delay = await self.db.get_setting(destination.guild.id, models.SettingsType.DELETE_GENERAL_DELAY)
        for page in self.paginator.pages:
            if delete_delay >= 0:
                await destination.send(page, delete_after=delete_delay)
            else:
                await destination.send(page)
