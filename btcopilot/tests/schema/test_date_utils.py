import datetime

from btcopilot.schema import (
    BLANK_DATE_TEXT,
    BLANK_TIME_TEXT,
    validatedDateTimeText,
    pyDateTimeString,
)


def test_validatedDateTimeText_empty():
    assert validatedDateTimeText("") is None


def test_validatedDateTimeText_blank():
    assert validatedDateTimeText(BLANK_DATE_TEXT) is None


def test_validatedDateTimeText_standard_format():
    result = validatedDateTimeText("03/15/2024")
    assert result is not None
    assert result.date().year() == 2024
    assert result.date().month() == 3
    assert result.date().day() == 15


def test_validatedDateTimeText_with_time():
    result = validatedDateTimeText("03/15/2024", "2:30 pm")
    assert result is not None
    assert result.time().hour() == 14
    assert result.time().minute() == 30


def test_validatedDateTimeText_blank_time():
    result = validatedDateTimeText("03/15/2024", BLANK_TIME_TEXT)
    assert result is not None
    assert result.date().year() == 2024


def test_validatedDateTimeText_8digit_format():
    result = validatedDateTimeText("03/15/24")
    assert result is not None
    assert result.date().month() == 3
    assert result.date().day() == 15


def test_pyDateTimeString_datetime():
    dt = datetime.datetime(2024, 3, 15, 14, 30)
    result = pyDateTimeString(dt)
    assert "03/15/2024" in result
    assert "02:30 PM" in result


def test_pyDateTimeString_from_string():
    result = pyDateTimeString("2024-03-15 14:30:00")
    assert "03/15/2024" in result
    assert "02:30 PM" in result
