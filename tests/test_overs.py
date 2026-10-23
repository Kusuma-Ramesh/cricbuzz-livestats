import pytest

from utils import overs


def test_notation_roundtrip():
    assert overs.to_balls("4.3") == 27
    assert overs.to_notation(27) == "4.3"
    assert overs.to_notation(24) == "4.0"


@pytest.mark.parametrize("bad", ["4.6", "4.7", "abc", "-1", "4.55"])
def test_rejects_impossible_notation(bad):
    with pytest.raises(ValueError):
        overs.to_balls(bad)


def test_economy_uses_legal_balls():
    assert overs.economy(30, 27) == 6.67
    assert overs.economy(10, 0) is None
