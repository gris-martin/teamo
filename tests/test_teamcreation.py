from datetime import datetime

import pytest

from teamo import models, teamcreation


@pytest.fixture
def entry_and_teams():
    entry = models.Entry(
        message_id=0,
        channel_id=0,
        server_id=0,
        game="Test game",
        start_date=datetime.now(),
        max_players=5
    )
    entry_and_teams = {
        "entry": entry,
        "teams": None
    }
    yield entry_and_teams

    # Sanity test the embed creation
    embed = teamcreation.create_finish_embed(entry)
    teams = entry_and_teams["teams"]
    if len(entry.members) > 0:
        assert len(embed.fields) == len(teams)
    else:
        assert len(embed.fields) == 1

def test_generate_name():
    name = teamcreation.generate_name()
    names = name.split()
    assert len(names) == 2
    with open(teamcreation.adjectives_filename) as f:
        lines = f.read().splitlines()
        assert names[0].lower() in lines
    with open(teamcreation.noun_filename) as f:
        lines = f.read().splitlines()
        assert names[1].lower() in lines

def test_create_teams_5(entry_and_teams):
    entry = entry_and_teams["entry"]
    entry.members.append(models.Member(0, 1))
    entry.members.append(models.Member(0, 2))
    entry.members.append(models.Member(0, 3))
    entry.members.append(models.Member(0, 4))

    # Should create 2 teams with 5 in each (1+4, 2+3)
    teams = teamcreation.create_teams(entry)
    assert len(teams) == 2
    assert teams[0].get_num_players() == 5
    assert teams[1].get_num_players() == 5
    entry_and_teams["teams"] = teams

def test_create_teams_4(entry_and_teams):
    entry = entry_and_teams["entry"]
    entry.max_players = 4
    entry.members.append(models.Member(0, 1))
    entry.members.append(models.Member(0, 1))
    entry.members.append(models.Member(0, 2))
    entry.members.append(models.Member(0, 2))
    entry.members.append(models.Member(0, 3))

    # Should create 3 teams with 3 in each (1+2, 1+2, 3)
    teams = teamcreation.create_teams(entry)
    assert len(teams) == 3
    for team in teams:
        assert team.get_num_players() == 3
    entry_and_teams["teams"] = teams

def test_create_teams_3(entry_and_teams):
    entry = entry_and_teams["entry"]
    entry.max_players = 3
    entry.members.append(models.Member(0, 1))
    entry.members.append(models.Member(0, 2))
    entry.members.append(models.Member(0, 1))
    entry.members.append(models.Member(0, 1))
    entry.members.append(models.Member(0, 2))
    entry.members.append(models.Member(0, 1))
    entry.members.append(models.Member(0, 2))

    # Should create 4 teams: 1+2, 1+2, 1+1, 2
    teams = teamcreation.create_teams(entry)
    assert len(teams) == 4
    teams_2 = list(filter(lambda t: t.get_num_players() == 2, teams))
    teams_3 = list(filter(lambda t: t.get_num_players() == 2, teams))
    assert len(teams_2) == 2
    assert len(teams_3) == 2
    entry_and_teams["teams"] = teams

def test_create_no_teams(entry_and_teams):
    pass
