from ghtp_null_agents.lookup_builder import extract_login
from tests.fixtures import user_json

import pytest




class TestExtractLogin:

    def test_graphql_user_object(self):
        assert extract_login(user_json("avanhoorn")) == "avanhoorn"

    @pytest.mark.parametrize("login",[
        ("avanhoorn"),
        ("baldygeezer"),])
    def test_plain_login_string_is_rejected(self, login):
        # we should see logins being checked. If we do something is wrong and we don't want to be assigning a login to
        # anything so it should return none
        assert extract_login(login) is None


    @pytest.mark.parametrize("falsy", [None, {}, "", False])
    def test_unresolved_returns_none(self, falsy):
        assert extract_login(falsy) is None

    @pytest.mark.parametrize("login",[user_json("dependabot", typename="Bot"),
                                      user_json("myclevercithing", typename="Bot")])
    def test_bot_is_skipped(self,login):
        # Mapping a human name onto a bot login would poison the lookup.
        assert extract_login(login) is None