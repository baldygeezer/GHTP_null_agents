from pathlib import Path

import pytest
from rdflib import URIRef

from ghtp_null_agents.resolve_orphan_commits import resolve_agent_uri, DEFAULT_AGENT_BASE
from tests.fixtures import user_json, commit, person

SCRIPT = Path(__file__).resolve().parent.parent / "ghtp_null_agents" / "resolve_orphan_commits.py"
BASE = DEFAULT_AGENT_BASE


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