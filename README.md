# TeamoPy
Teamo written in Python :)

## Commands

- **Create** - `@Teamo create <date/time> <maxPlayersPerTeam> <game>`
- **Edit game** - `@Teamo edit game <game>`
- **Edit max players** - `@Teamo edit maxPlayers|players <maxPlayersPerTeam>`
- **Edit date or time** - `@Teamo edit date|time <date/time>`
- **Cancel** - `@Teamo delete|remove|cancel <id>`

## Translation

- New translation from template: `pybabel init -D base -d locales -l sv -i locales\base.pot`
- Compile `.po` to `.mo`: `pybabel compile -D base -d locales -l sv`
- Update catalogs from POT file: `pybabel update -i locales\base.pot -d locales -D base`
- Extract strings from file: `pybabel extract -o locales\base.pot teamo.py`
