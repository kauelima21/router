import datetime
import json
from decimal import Decimal

from router.utils import DecimalEncoder, json_dumps


def test_encodes_decimal_integer():
    result = json_dumps({"count": Decimal("10")})

    assert result == '{"count": 10}'


def test_encodes_decimal_float():
    result = json_dumps({"price": Decimal("9.99")})

    assert result == '{"price": 9.99}'


def test_encodes_datetime():
    dt = datetime.datetime(2026, 4, 11, 15, 30, 0)
    result = json_dumps({"created_at": dt})

    assert '"2026-04-11T15:30:00"' in result


def test_encodes_date():
    d = datetime.date(2026, 4, 11)
    result = json_dumps({"date": d})

    assert '"2026-04-11"' in result


def test_sort_keys():
    result = json_dumps({"b": 1, "a": 2}, sort_keys=True)

    assert result == '{"a": 2, "b": 1}'


def test_raises_on_non_serializable():
    with pytest.raises(TypeError):
        json_dumps({"obj": object()})


import pytest
