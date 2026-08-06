from pathlib import Path

import pytest
from rdflib import URIRef

from ghtp_null_agents.resolve_orphan_commits import resolve_agent_uri, DEFAULT_AGENT_BASE, resolve_identifier, \
    MintRegistry
from tests.fixtures import user_json, commit, person

SCRIPT = Path(__file__).resolve().parent.parent / "ghtp_null_agents" / "resolve_orphan_commits.py"
BASE = DEFAULT_AGENT_BASE

def empty_lookup(by_name=None, by_email=None):
    return {"by_name": by_name or {}, "by_email": by_email or {}}

class TestResolveAgentUri:
    def test_plain_login_becomes_github_url(self):
        assert resolve_agent_uri("avanhoorn") == URIRef("https://github.com/avanhoorn")

    def test_login_case_is_preserved(self):
        assert resolve_agent_uri("ChristianWulf") == URIRef("https://github.com/ChristianWulf")

    def test_bare_email_becomes_mailto(self):
        assert resolve_agent_uri("pbr@informatik.uni-kiel.de") == URIRef("mailto:pbr@informatik.uni-kiel.de")

    def test_already_prefixed_mailto_is_not_double_prefixed(self):
        assert resolve_agent_uri("mailto:x@y.de") == URIRef("mailto:x@y.de")

    def test_http_value_is_used_verbatim(self):
        # pin a manually-curated agent to a minted PARS URI.
        assert resolve_agent_uri(BASE + "ninamarwede") == URIRef(BASE + "ninamarwede")

    def test_manual_id_is_used_verbatim(self):
        # pin a manually-curated agent to a minted PARS URI.
        assert resolve_agent_uri(BASE + "ninamarwede") == URIRef(BASE + "ninamarwede")


class TestResolveIdentifier:
    def test_matches_on_name(self):
        lookup = empty_lookup(by_name={"andre van hoorn": "avanhoorn"})
        assert resolve_identifier(name = "André van Hoorn", email=None, lookup=lookup) == ("avanhoorn", "lookup-name")

    def test_falls_back_to_email(self):
        lookup = empty_lookup(by_email={"nie@informatik.uni-kiel.de": "nils-christian"})
        assert resolve_identifier("Nils Christian Ehmke", "nie@informatik.uni-kiel.de", lookup) == ("nils-christian", "lookup-email")

    def test_name_takes_priority_over_email(self):
        lookup = empty_lookup(by_name={"real person": "name-login"},
                              by_email={"shared@x.de": "email-login"})
        assert resolve_identifier("Real Person", "shared@x.de", lookup)[0] == "name-login"

    def test_returns_none_when_both_miss(self):
        assert resolve_identifier("Nobody", "n@x.de", empty_lookup()) == (None, None)


class TestMintRegistry:
    def test_mints_deterministic_uri(self):
        r = MintRegistry(BASE)
        uri = r.mint(slug = "ninamarwede",
                     name = "Nina Marwede",
                     email = "nina@x.de",
                     commit_url = "u1",
                     role = "author")
        assert uri == URIRef(BASE + "ninamarwede")

    def test_same_name_and_email_is_not_a_conflict(self):
        r = MintRegistry(BASE)
        r.mint("ninamarwede", "Nina Marwede", "nina.marwede@uni-oldenburg.de", "u1", "author")
        r.mint("ninamarwede", "Nina Marwede", "nina.marwede@uni-oldenburg.de", "u1", "committer")
        review = r.review()
        assert review["name_email_conflicts"] == []
        assert review["email_name_conflicts"] == []
        assert review["minted"][0]["slots"] == 2

