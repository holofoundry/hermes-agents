import pytest
from datetime import date
from massive_forex_mcp.utils import (
    clean_currency,
    clean_forex_ticker,
    resolve_week_date_range,
    parse_date
)

def test_clean_currency_valid():
    assert clean_currency("usd") == "USD"
    assert clean_currency(" EUR ") == "EUR"
    assert clean_currency("gbp") == "GBP"

def test_clean_currency_invalid():
    with pytest.raises(ValueError, match="Currency code must be three letters"):
        clean_currency("USDT")
    with pytest.raises(ValueError, match="Currency code must be three letters"):
        clean_currency("123")
    with pytest.raises(ValueError, match="Currency code must be three letters"):
        clean_currency("US")

def test_clean_forex_ticker_valid():
    assert clean_forex_ticker("EURUSD") == "C:EURUSD"
    assert clean_forex_ticker("eur/usd") == "C:EURUSD"
    assert clean_forex_ticker("GBP-USD") == "C:GBPUSD"
    assert clean_forex_ticker("USD_JPY") == "C:USDJPY"
    assert clean_forex_ticker("C:AUDNZD") == "C:AUDNZD"
    assert clean_forex_ticker("EUR USD") == "C:EURUSD"

def test_clean_forex_ticker_invalid():
    with pytest.raises(ValueError, match="Forex ticker must be a 6-letter pair"):
        clean_forex_ticker("EURUSDT")
    with pytest.raises(ValueError, match="Forex ticker must be a 6-letter pair"):
        clean_forex_ticker("USD")

def test_parse_date():
    assert parse_date("2024-01-01", "test_field") == date(2024, 1, 1)
    with pytest.raises(ValueError, match="test_field must be a YYYY-MM-DD date"):
        parse_date("01-01-2024", "test_field")

def test_resolve_week_date_range_explicit():
    start, end, source = resolve_week_date_range(
        from_date="2024-01-01",
        to_date="2024-01-07",
        week_number=None,
        year=None,
        relative_week="last"
    )
    assert start == date(2024, 1, 1)
    assert end == date(2024, 1, 7)
    assert source == "date_range"

def test_resolve_week_date_range_iso_week():
    # ISO week 1 of 2024 starts on 2024-01-01 (Monday)
    start, end, source = resolve_week_date_range(
        from_date=None,
        to_date=None,
        week_number=1,
        year=2024,
        relative_week="last"
    )
    assert start == date(2024, 1, 1)
    assert end == date(2024, 1, 7)
    assert source == "iso_week"

def test_resolve_week_date_range_errors():
    with pytest.raises(ValueError, match="from_date and to_date must be provided together"):
        resolve_week_date_range(from_date="2024-01-01", to_date=None, week_number=None, year=None, relative_week="last")
    
    with pytest.raises(ValueError, match="from_date must be on or before to_date"):
        resolve_week_date_range(from_date="2024-01-07", to_date="2024-01-01", week_number=None, year=None, relative_week="last")

    with pytest.raises(ValueError, match="week_number must be between 1 and 53"):
        resolve_week_date_range(from_date=None, to_date=None, week_number=54, year=2024, relative_week="last")
