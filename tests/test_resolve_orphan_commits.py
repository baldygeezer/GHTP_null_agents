from pathlib import Path

import pytest
from rdflib import URIRef

from ghtp_null_agents.resolve_orphan_commits import resolve_agent_uri
from tests.fixtures import user_json, commit, person

SCRIPT = Path(__file__).resolve().parent.parent / "ghtp_null_agents" / "resolve_orphan_commits.py"



class TestResolveAgentUri:
    def test_plain_login_becomes_github_url(self):
        assert resolve_agent_uri("avanhoorn") == URIRef("https://github.com/avanhoorn")