import json
import subprocess
import sys

import pytest
from pathlib import Path

from rdflib import Graph, URIRef, RDF, PROV

from tests.fixtures import commit, person, user_json, kieker_commits
from ghtp_null_agents.lookup_builder import LookupBuilder, process_commits
from ghtp_null_agents.resolve_orphan_commits import resolve_identifier, G2P, DEFAULT_AGENT_BASE

ROOT=Path(__file__).resolve().parent.parent
BUILD=ROOT / "ghtp_null_agents" / "lookup_builder.py"
RESOLVE = ROOT / "ghtp_null_agents" / "resolve_orphan_commits.py"


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

@pytest.mark.usefixtures("kieker_commits")
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


class TestFullCliWorkflow:

    def _workflow(self, tmp_path, commits):
        commits_path= tmp_path / "commits.json"
        commits_path.write_text(json.dumps(commits, ensure_ascii=False), encoding="utf-8")
        lookup_path= tmp_path / "lookup.json"
        conflicts_path= tmp_path  / "conflicts.json"
        out_ttl = tmp_path / "orphans.ttl"


        build= subprocess.run(
            [sys.executable, str(BUILD), "--commits", str(commits_path), "--lookup",str(lookup_path), "--conflicts", conflicts_path],
            capture_output = True, text=True,
        )

        assert build.returncode == 0, build.stderr

        resolve= subprocess.run(
            [sys.executable, str(RESOLVE ), "--commits", str(commits_path), "--lookup",str(lookup_path), "--output", str(out_ttl)],
            capture_output = True, text=True,
        )

        assert  resolve.returncode == 0, resolve.stderr

        g = Graph()
        g.parse(out_ttl, format = "turtle")

        return build, resolve, g, tmp_path / "orphans_unresolved.json"

    def test_end_to_end_on_kieker_slice(self, tmp_path, kieker_commits):
        _, _, g, unresolved_path = self._workflow(tmp_path, kieker_commits)

        avh = URIRef("https://github.com/avanhoorn")
        nce = URIRef("https://github.com/nils-christian")
        assert (avh, RDF.type, PROV.Agent) in g
        assert (nce, RDF.type, PROV.Agent) in g

        # Both orphan commits attributed, each with author + committer roles.
        for commit_url in (
                "https://github.com/kieker-monitoring/kieker/commit/25853fd8",
                "https://github.com/kieker-monitoring/kieker/commit/78656f09",
        ):
            roles = {
                g.value(q, PROV.hadRole)
                for q in g.objects(URIRef(commit_url), PROV.qualifiedAssociation)
            }
            assert roles == {G2P["author"], G2P["committer"]}

        # Nobody is left unattributed any more -- the unknown contributor is minted into the agents namespace instead.
        assert json.loads(unresolved_path.read_text(encoding="utf-8")) == []
        assert (URIRef(DEFAULT_AGENT_BASE + "avantaclue"), RDF.type, PROV.Agent) in g

    def test_manual_lookup_entries_survive_and_are_used(self, tmp_path):
        """
        Names that can never be auto-resolved get added to lookup.json by
        hand. Check the three manual value shapes all mint sane URIs.
        """
        commits = [
            commit("https://x/commit/1", person("Nina Marwede", "nina@x.de", None)),
            commit("https://x/commit/2", person("Pascale Brandt", "pbr@informatik.uni-kiel.de", None)),
            commit("https://x/commit/3", person("Wilhelm", "wh@x.de", None)),
        ]
        commits_path = tmp_path / "commits.json"
        commits_path.write_text(json.dumps(commits, ensure_ascii=False), encoding="utf-8")

        lookup_path = tmp_path / "lookup.json"
        lookup_path.write_text(json.dumps({
            "by_name": {
                "nina marwede": "svn:nina",  # synthetic id
                "pascale brandt": "pbr@informatik.uni-kiel.de",  # email only
                "wilhelm": "whasselbring",  # github login
            },
            "by_email": {},
        }, ensure_ascii=False), encoding="utf-8")

        out_ttl = tmp_path / "orphans.ttl"
        proc = subprocess.run(
            [sys.executable, str(RESOLVE),
                    "--commits", str(commits_path),
                    "--lookup",str(lookup_path),
                    "--output", str(out_ttl)],
            capture_output=True, text=True,
        )
        assert proc.returncode == 0, proc.stderr

        g = Graph()
        g.parse(out_ttl, format="turtle")
        agents = {str(a) for a in g.subjects(RDF.type, PROV.Agent)}
        assert agents == {
            "svn:nina",
            "mailto:pbr@informatik.uni-kiel.de",
            "https://github.com/whasselbring",
        }

    def test_rerun_after_filling_gaps_clears_the_unresolved_report(self, tmp_path):
        """The intended manual loop: run, inspect unresolved, patch the
        lookup, re-run, get a clean report."""
        commits = [commit("https://x/commit/1", person("Mystery Person", "mp@x.de", None))]
        commits_path = tmp_path / "commits.json"
        commits_path.write_text(json.dumps(commits, ensure_ascii=False), encoding="utf-8")
        lookup_path = tmp_path / "lookup.json"
        out_ttl = tmp_path / "orphans.ttl"
        unresolved_path = tmp_path / "orphans_unresolved.json"

        review_path = tmp_path / "orphans_review.json"

        lookup_path.write_text(json.dumps({"by_name": {}, "by_email": {}}), encoding="utf-8")
        subprocess.run(
            [sys.executable, str(RESOLVE),
                    "--commits", str(commits_path),
                    "--lookup", str(lookup_path),
                    "--output", str(out_ttl)],
                    capture_output=True, text=True, check=True)

        g = Graph()
        g.parse(out_ttl, format="turtle")
        assert (URIRef(DEFAULT_AGENT_BASE + "mysteryperson"), RDF.type, PROV.Agent) in g
        assert [m["slug"] for m in json.loads(review_path.read_text(encoding="utf-8"))["minted"]] == ["mysteryperson"]

        # Once a GitHub account is discovered and added by hand, the lookup
        # takes over and nothing is minted for that person any more.
        lookup_path.write_text(json.dumps({"by_name": {"mystery person": "mystery-login"}, "by_email": {}}),
                               encoding="utf-8")
        subprocess.run([sys.executable, str(RESOLVE),
                        "--commits", str(commits_path),
                        "--lookup", str(lookup_path),
                        "--output", str(out_ttl)],
                        capture_output=True, text=True, check=True)
        g = Graph();
        g.parse(out_ttl, format="turtle")
        assert (URIRef("https://github.com/mystery-login"), RDF.type, PROV.Agent) in g
        assert (URIRef(DEFAULT_AGENT_BASE + "mysteryperson"), RDF.type, PROV.Agent) not in g
        assert json.loads(review_path.read_text(encoding="utf-8"))["minted"] == []

    def test_empty_commits_file_produces_empty_output(self, tmp_path):
        _, _, g, unresolved_path = self._workflow(tmp_path, [])
        assert len(g) == 0
        assert json.loads(unresolved_path.read_text(encoding="utf-8")) == []