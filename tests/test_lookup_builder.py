from ghtp_null_agents.lookup_builder import extract_login, LookupBuilder
from tests.fixtures import user_json

import pytest




class TestExtractLogin:

    def test_graphql_user_object(self):
        assert extract_login(user_json("avanhoorn")) == "avanhoorn"

    @pytest.mark.parametrize("login",[
        ("avanhoorn"),
        ("baldygeezer"),])
    def test_plain_login_string_is_rejected(self, login):
        # we should see logins being checked. If we do something is wrong, and we don't want to be assigning a login to
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

    def test_preserves_login_case(self):
        # github2prov treats logins as case-sensitive.
        assert extract_login(user_json("ChristianWulf")) == "ChristianWulf"

class TestLookupBuilder:
    def test_records_name_and_email(self):
        b = LookupBuilder()
        b.add("André van Hoorn", "AVH@X.de", "avanhoorn")
        assert b.by_name == {"andre van hoorn": "avanhoorn"}
        assert b.by_email == {"avh@x.de": "avanhoorn"}

    def test_login_case_is_preserved_in_values(self):
        # ... because now we are matching - we don't want case in emails to break a match, and github2prov treats github
        # user slugs as case-sensitive
        b = LookupBuilder()
        b.add("christian wulf", "cw@x.de", "ChristianWulf",)
        assert b.by_name["christian wulf"] == "ChristianWulf"

    def test_missing_name_still_records_email(self):
        b = LookupBuilder()
        b.add(None, "only@email.de", "someone")
        assert b.by_name == {}
        assert b.by_email == {"only@email.de": "someone"}

    def test_missing_email_still_records_name(self):
        b = LookupBuilder()
        b.add("Only Name", None, "someone")
        assert b.by_name == {"only name": "someone"}
        assert b.by_email == {}

    def test_blank_name_is_not_recorded_as_empty_key(self):
        b = LookupBuilder()
        b.add("   ", "x@y.de", "someone")
        assert "" not in b.by_name

    def test_first_seen_login_wins_in_the_table(self):
        b = LookupBuilder()
        b.add("Ambiguous Name", None, "first-login",)
        b.add("Ambiguous Name", None, "second-login")
        b.add("brian", None, "another_login")
        b.add("Ambiguous Name", None, "third-login")
        assert b.by_name["ambiguous name"] == "first-login"
        assert b.by_name["brian"] == "another_login"

    def test_conflicting_name_is_reported(self):
        b = LookupBuilder()
        b.add("Ambiguous Name", None, "first-login")
        b.add("Ambiguous Name", None, "second-login")

        conflicts = b.conflicts()
        assert len(conflicts) == 1
        c = conflicts[0]
        assert c["field"] == "name"
        assert c["normalized_key"] == "ambiguous name"
        assert c["logins_seen"] == ["first-login", "second-login"]

    def test_conflicting_email_is_reported(self):
        b = LookupBuilder()
        b.add(None, "shared@x.de", "login-one")
        b.add(None, "SHARED@X.de", "login-two")

        conflicts = b.conflicts()
        assert len(conflicts) == 1
        assert conflicts[0]["field"] == "email"
        assert conflicts[0]["normalized_key"] == "shared@x.de"

    def test_two_names_sharing_one_login_is_not_a_conflict(self):
        # normal: one person commits under several spellings.
        b = LookupBuilder()
        b.add("Nils Ehmke", None, "nils-christian")
        b.add("Nils Christian Ehmke", None, "nils-christian")
        assert b.conflicts() == []
        assert len(b.by_name) == 2