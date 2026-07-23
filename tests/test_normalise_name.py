import pytest
from ghtp_null_agents.normalise_names import normalise_name


class TestNormaliseName:

    @pytest.mark.parametrize("raw,expected", [
        ("Andre van Hoorn", "andre van hoorn"),
        ("ANDRE VAN HOORN", "andre van hoorn"),
        ("andre van hoorn", "andre van hoorn"),
        ("AnDrE VaN hOoRn", "andre van hoorn"),
    ])
    def test_fixes_case(self, raw, expected):
        assert normalise_name(raw) == expected
