from filingtext.pit import pit_dates


def test_pit_available_date_is_next_calendar_day():
    announce, available = pit_dates("2024-04-02")
    assert announce == "2024-04-02"
    assert available == "2024-04-03"
