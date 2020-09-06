# TeamoPy
A Discord bot for creating teams and finding people to play with :)

## Using Teamo
Teamo is a Discord bot that can be used to create teams of a certain size at a certain time. The main Teamo command looks like this:

```
@Teamo create <number of players per team> <time> <game>
```
where
- **\<number of players per team\>** is the number of players per team for the particular game.
- **\<time\>** is the time to start the game, of the form hh:mm.
- **\<game\>** is the name of the game.

For example:
```
@Teamo create 5 23:05 League of Legends
```

will create a Teamo for 23:05 with 5 players in each team. The game name, League of Legends, is only used to show which game will be played.

### The "waiting" message
When a `create` command has been sent, a message looking something like this will be displayed (given that the command was successful)

![Waiting message](docs/readme/waiting.PNG)

To register for playing, press a number reaction at the bottom, with the number of players who will be joining from your group. E.g. if you and a friend wants to register to be in the same team, you can press the 2️⃣ reaction, and your friend doesn't have to press anything. If you find another friend and want to change the number of players in your group, just press another reaction and the registration will update automatically.

In this example I got some help from my bot friends to demonstrate :)

If you want to cancel the registration, press the ❌ reaction. The message will be deleted after 15 seconds.


### The "finished" message
Once the time has run out, Teamo will remove the old message and post a new message with everyone divided into teams. The teams will be created to be as few as possible and as equal as possible and will be given unique names. In this case Teamo decided that 3 teams with 4 in each was the best alternative. DJ Sona seems to be on her own, but she has 3 friends from before so she will be okay :)

Teamo will mention everyone so no one should miss the event.

![Finished message](docs/readme/finished.PNG)

Good luck and have fun in the game!

### Commands

- **Create** - `@Teamo create <date/time> <maxPlayersPerTeam> <game>`
- **Edit game** - `@Teamo edit game <game>`
- **Edit max players** - `@Teamo edit maxPlayers|players <maxPlayersPerTeam>`
- **Edit date or time** - `@Teamo edit date|time <date/time>`
- **Cancel** - `@Teamo delete|remove|cancel <id>`

## Developing
### Quick-start guide
To work with Teamo, I recommend doing the following steps in a terminal:

- Set the `TEAMO_BOT_TOKEN` environment variable to the Bot token acquired from the [Discord Developer Portal](https://discord.com/developers/applications).
- (Install Python >3.8 if not already installed)
- Clone the teamo repository
- Create a virtual environment
- Install Teamo in edit mode (otherwise the scripts will not have the paths setup correctly)

These steps can be done using these console commands (given that `python` is the path to your Python 3.8 installation):
```
python -m pip install virtualenv
python -m virtualenv venv
python -m pip install --update pip setuptools wheel
pip install -e .
```

Teamo can then be run using `python -m teamo` or `python teamo/app.py`

### Testing
Teamo uses [pytest](https://docs.pytest.org/en/stable/) for unittests. To run the tests, do these steps:

- Install pytest
- Run pytest

```
python -m pip install pytest pytest-asyncio
pytest
```

### Teamo with Visual Studio Code
The [Python plugin](https://marketplace.visualstudio.com/items?itemName=ms-python.python) for Visual Studio Code allows debugging scripts and tests.

I recommend setting the `TEAMO_BOT_TOKEN` environment variable in a terminal and starting Visual Studio Code from the same terminal.

#### Debugging Teamo
To debug scripts (such as the main script `teamo/app.py`) the following `launch.json` configuration can be used:

```json
{
    "configurations": [
        {
            "name": "Python: Teamo",
            "type": "python",
            "request": "launch",
            "program": "teamo/__main__.py",
            "console": "integratedTerminal"
        }
    ]
}
```

#### Debugging tests
To debug tests, you first have to configure the test runner by running `Python: Configure Tests` from the Command Palette (`Ctrl + Shift + P`). This will add an icon to the left (with a conical flask shape) where tests can be started and debugged.


### Contributing

Issues and pull requests are welcome :) One easy way to help out is to expand the nouns and adjectives in the `lists/nouns.list` and `lists/adjectives.list` files. They will be used when creating the teams!