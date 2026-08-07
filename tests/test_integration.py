
import pytest
from pathlib import Path
from fixtures import commit, person, user_json
from ghtp_null_agents.lookup_builder import LookupBuilder, process_commits
from ghtp_null_agents.resolve_orphan_commits import resolve_identifier


@pytest.mark.parametrize("resolved_name,orphan_name", [
    ("Andre van Hoorn", "André van Hoorn"),
    ("André van Hoorn", "Andre van Hoorn"),
    ("Armin Möbius", "ARMIN MOBIUS"),
    ("Björn Weißenfels", "Bjorn Weissenfels"),
    ("Clemens Kurz", "Clemens Kurz "),
    ("Jürgen  Walter", "jurgen walter"),
])
def test_builder_keys_are_findable_by_resolver(resolved_name, orphan_name):
    """A name harvested by the builder must be resolvable by the resolver
    under any spelling that normalises to the same key."""
    builder = LookupBuilder()
    builder.add(name=resolved_name, email=None, login = "loginmcloginface", commit_url = "u1", role = "author")
    lookup = {"by_name": builder.by_name, "by_email": builder.by_email}

    assert resolve_identifier(name = orphan_name, email = None, lookup = lookup)[0] == "loginmcloginface"


def test_builder_email_keys_are_findable_by_resolver():
    builder = LookupBuilder()
    builder.add(name = None, email = "AVH@Informatik.Uni-Kiel.DE", login = "avanhoorn", commit_url = "u1", role = "author")
    lookup = {"by_name": builder.by_name, "by_email": builder.by_email}

    assert resolve_identifier(None, "avh@informatik.uni-kiel.de", lookup)[0] == "avanhoorn"


def test_in_process_round_trip_resolves_expected_agents(kieker_commits):
    builder = LookupBuilder()
    process_commits(kieker_commits, builder)
    lookup = {"by_name": builder.by_name, "by_email": builder.by_email}

    # Orphan resolvable by name, once diacritics are dealt with .
    assert resolve_identifier("André van Hoorn", "avh@informatik.uni-kiel.de", lookup)[0] == "avanhoorn"
    # Orphan resolvable only via its email (name spelled differently).
    assert resolve_identifier("Nils Christian Ehmke", "nie@informatik.uni-kiel.de", lookup)[0] == "nils-christian"
    # Genuinely unknown -- must stay unresolved.
    assert resolve_identifier("Aven Taclue", "tup@nowhere.de", lookup) == (None, None)