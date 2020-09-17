from datetime import datetime, timedelta
from time import time
import itertools

from dateutil import tz
import pytest

from teamo import utils

tznames = [
    "Europe/Stockholm",
    "America/Santiago",
    "Pacific/Easter",
    "Asia/Tokyo",
    "Asia/Tehran",
    "Etc/UTC",
    "Etc/GMT"
]

date_string_tds = [
    timedelta(minutes=1),
    timedelta(hours=1),
    timedelta(days=1),
    timedelta(minutes=-1),
    timedelta(hours=-1),
    timedelta(days=-1),
]

date_string_params = itertools.product(tznames, date_string_tds)

@pytest.mark.parametrize("tzname, timediff", date_string_params)
def test_get_date_string(tzname: str, timediff: timedelta):
    now = datetime.now(tz=tz.gettz(tzname))

    date1 = now + timediff
    date1_str = utils.get_date_string(date1)
    if date1.day == now.day:
        assert "today" in date1_str
    elif date1.day == now.day + 1:
        assert "tomorrow" in date1_str
    else:
        assert "tomorrow" not in date1_str and "today" not in date1_str



timedelta_string_params = [
    (timedelta(seconds=10), "<1 min"),
    (timedelta(seconds=59), "<1 min"),
    (timedelta(seconds=60), "1 min"),
    (timedelta(minutes=12), "12 min"),
    (timedelta(hours=10, minutes=33), "10 h 33 min"),
    (timedelta(days=13, minutes=66), "13 days 1 h 6 min"),
]

@pytest.mark.parametrize("td, expected", timedelta_string_params)
def test_get_timedelta_string(td: timedelta, expected: str):
    td_str = utils.get_timedelta_string(td)
    assert td_str == expected
