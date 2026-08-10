import json
import subprocess
import sys
from pathlib import Path

import pytest
from rdflib import URIRef, Graph, RDF, PROV, RDFS, Literal

from ghtp_null_agents.resolve_orphan_commits import resolve_agent_uri, DEFAULT_AGENT_BASE, resolve_identifier, \
    MintRegistry, process_slot, G2P, WEB_UI_SLUG
from tests.fixtures import commit, person, kieker_commits

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
        assert resolve_identifier(name="André van Hoorn", email=None, lookup=lookup) == ("avanhoorn", "lookup-name")

    def test_falls_back_to_email(self):
        lookup = empty_lookup(by_email={"nie@informatik.uni-kiel.de": "nils-christian"})
        assert resolve_identifier("Nils Christian Ehmke", "nie@informatik.uni-kiel.de", lookup) == ("nils-christian",
                                                                                                    "lookup-email")

    def test_name_takes_priority_over_email(self):
        lookup = empty_lookup(by_name={"real person": "name-login"},
                              by_email={"shared@x.de": "email-login"})
        assert resolve_identifier("Real Person", "shared@x.de", lookup)[0] == "name-login"

    def test_returns_none_when_both_miss(self):
        assert resolve_identifier("Nobody", "n@x.de", empty_lookup()) == (None, None)


class TestMintRegistry:
    def test_mints_deterministic_uri(self):
        r = MintRegistry(BASE)
        uri = r.mint(slug="ninamarwede",
                     name="Nina Marwede",
                     email="nina@x.de",
                     commit_url="u1",
                     role="author")
        assert uri == URIRef(BASE + "ninamarwede")

    def test_same_name_and_email_is_not_a_conflict(self):
        r = MintRegistry(BASE)
        r.mint("ninamarwede", "Nina Marwede", "nina.marwede@uni-oldenburg.de", "u1", "author")
        r.mint("ninamarwede", "Nina Marwede", "nina.marwede@uni-oldenburg.de", "u1", "committer")
        review = r.review()
        assert review["name_email_conflicts"] == []
        assert review["email_name_conflicts"] == []
        assert review["minted"][0]["slots"] == 2

    def test_one_name_two_emails_is_flagged_as_possible_false_merge(self):
        #  Nina at uni-oldenburg vs Nina at soton -- probably the same person, but needs manual review
        r = MintRegistry(BASE)
        r.mint("ninamarwede", "Nina Marwede", "nina.marwede@uni-oldenburg.de", "u1", "author")
        r.mint("ninamarwede", "Nina Marwede", "nina.marwede@soton.ac.uk", "u2", "author")

        conflicts = r.review()["name_email_conflicts"]
        assert len(conflicts) == 1
        assert conflicts[0]["slug"] == "ninamarwede"
        assert conflicts[0]["emails"] == ["nina.marwede@soton.ac.uk", "nina.marwede@uni-oldenburg.de"]
        assert conflicts[0]["uri"] == BASE + "ninamarwede"

    def test_false_merge_conflict_carries_inf(self):
        r = MintRegistry(BASE)
        r.mint("ninamarwede", "Nina Marwede", "a@x.de", "commit-a", "author")
        r.mint("ninamarwede", "Nina Marwede", "b@x.de", "commit-b", "committer")

        occurrencess = r.review()["name_email_conflicts"][0]["occurrences"]
        assert {o["commit_url"] for o in occurrencess} == {"commit-a", "commit-b"}
        assert {o["email"] for o in occurrencess} == {"a@x.de", "b@x.de"}

    def test_one_email_two_names_is_flagged_as_possible_false_split(self):
        # The mirror risk: same human, inconsistent name spelling, so the
        # name-based URI splits them in two.
        r = MintRegistry(BASE)
        r.mint("ninamarwede", "Nina Marwede", "nina@x.de", "u1", "author")
        r.mint("nmarwede", "N. Marwede", "nina@x.de", "u2", "author")

        conflicts = r.review()["email_name_conflicts"]
        assert len(conflicts) == 1
        assert conflicts[0]["email"] == "nina@x.de"
        assert conflicts[0]["slugs"] == ["ninamarwede", "nmarwede"]
        assert conflicts[0]["uris"] == [BASE + "ninamarwede", BASE + "nmarwede"]

    def test_email_matching_is_case_insensitive(self):
        r = MintRegistry(BASE)
        r.mint("ninamarwede", "Nina Marwede", "Nina@X.de", "u1", "author")
        r.mint("ninamarwede", "Nina Marwede", "nina@x.de", "u2", "author")
        assert r.review()["name_email_conflicts"] == []

    def test_minted_record_collects_all_name_spellings(self):
        r = MintRegistry(BASE)
        r.mint("ninamarwede", "Nina Marwede", "n@x.de", "u1", "author")
        r.mint("ninamarwede", "NINA MARWEDE", "n@x.de", "u2", "author")
        assert r.review()["minted"][0]["names"] == ["NINA MARWEDE", "Nina Marwede"]

    def test_missing_email_does_not_create_a_conflict(self):
        r = MintRegistry(BASE)
        r.mint("someone", "Someone", None, "u1", "author")
        r.mint("someone", "Someone", "s@x.de", "u2", "author")
        assert r.review()["name_email_conflicts"] == []

    def test_custom_base_is_honoured(self):
        r = MintRegistry("http://example.org/a/")
        assert r.mint("x", "X", None, "u1", "author") == URIRef("http://example.org/a/x")


class TestProcessSlot:
    def _run(self, name="Nina Marwede", email="nina@x.de", lookup=None, role="author",
             registry=None, base=BASE):
        g = Graph()
        unresolved = []
        stats = __import__("collections").defaultdict(int)
        registry = registry or MintRegistry(base)
        method = process_slot(
            graph=g, commit_url="https://github.com/o/r/commit/abc",
            person=person(name, email, None), role=role,
            lookup=lookup if lookup is not None else empty_lookup(),
            registry=registry, unresolved=unresolved, stats=stats,
        )
        return g, unresolved, method, registry

    def test_lookup_hit_uses_github_uri(self):
        lookup = empty_lookup(by_name={"nina marwede": "ninalogin"})
        g, _, method, _ = self._run(lookup=lookup)
        assert method == "lookup-name"
        assert (URIRef("https://github.com/ninalogin"), RDF.type, PROV.Agent) in g

    def test_miss_mints_a_pars_uri(self):
        graph, unresolved, method, _ = self._run()
        assert method == "minted"
        assert unresolved == []
        assert (URIRef(BASE + "ninamarwede"), RDF.type, PROV.Agent) in graph

    def test_minted_agent_is_labelled_with_the_raw_name(self):
        g, _, _, _ = self._run()
        assert (URIRef(BASE + "ninamarwede"), RDFS.label, Literal("Nina Marwede")) in g

    def test_minted_agent_gets_plain_and_qualified_association(self):
        g, _, _, _ = self._run()
        agent = URIRef(BASE + "ninamarwede")
        commit_uri = URIRef("https://github.com/o/r/commit/abc")
        assert (commit_uri, PROV.wasAssociatedWith, agent) in g
        qassoc = g.value(commit_uri, PROV.qualifiedAssociation)
        assert (qassoc, PROV.agent, agent) in g

    def test_lookup_overrides_minting(self):
        # The documented manual-curation route: add an entry, stop minting.
        lookup = empty_lookup(by_name={"nina marwede": "svn:nina"})
        g, _, method, registry = self._run(lookup=lookup)
        assert method == "lookup-name"
        assert (URIRef("svn:nina"), RDF.type, PROV.Agent) in g
        assert registry.review()["minted"] == []

    @pytest.mark.parametrize("role", ["author", "committer"])
    def test_had_role_is_a_resource_not_a_literal(self, role):
        # REGRESSION: roles were previously emitted as string literals.
        g, _, _, _ = self._run(role=role)
        roles = list(g.objects(None, PROV.hadRole))
        assert roles == [G2P[role]]
        assert isinstance(roles[0], URIRef)
        assert not isinstance(roles[0], Literal)

    @pytest.mark.parametrize("name,expected", [("Author McAuthorface", "author"),
                                               ("Committer McCommitterface", "committer")])
    def test_both_roles_processed(self, name, expected):
        g, _, _, _ = self._run(name=name, role=expected)
        roles = list(g.objects(None, PROV.hadRole))
        assert len(roles) == 1
        assert roles[0] == G2P[expected]

    def test_does_not_create_the_commit_activity_node(self):
        # The prov:Activity belongs to the main pipeline.
        g, _, _, _ = self._run()
        assert (URIRef("https://github.com/o/r/commit/abc"), RDF.type, PROV.Activity) not in g

    def test_unmintable_name_is_reported_not_resolved(self):
        g, unresolved, method, _ = self._run(name="张伟", email=None)
        assert method is None
        assert len(g) == 0
        assert unresolved[0]["reason"] == "name has no slug-able characters"

    def test_no_name_and_no_email_is_reported(self):
        g, unresolved, method, _ = self._run(name=None, email=None)
        assert method is None
        assert unresolved[0]["reason"] == "no name or email"

    def test_email_only_slot_can_still_resolve_via_lookup(self):
        lookup = empty_lookup(by_email={"only@x.de": "somelogin"})
        g, unresolved, method, _ = self._run(name=None, email="only@x.de", lookup=lookup)
        assert method == "lookup-email"
        assert (URIRef("https://github.com/somelogin"), RDF.type, PROV.Agent) in g

    def test_email_only_slot_cannot_be_minted(self):
        # Minting is name-based; there is no name to slug.
        g, unresolved, method, _ = self._run(name=None, email="only@x.de")
        assert method is None
        assert unresolved[0]["reason"] == "name has no slug-able characters"

    def test_by_name_resolved_commit_was_associated(self, kieker_commits):
        lookup = empty_lookup(by_name={"andre van hoorn": "avanhoorn"})
        g, _, method, _ = self._run(lookup=lookup, name="andre van hoorn", email="avh@dgrd.de", role="committer")
        commit_uri = URIRef("https://github.com/o/r/commit/abc")
        agent = URIRef("https://github.com/avanhoorn")
        assert (commit_uri, PROV.wasAssociatedWith, agent) in g

    def test_by_email_resolved_commit_was_associated(self, kieker_commits):
        lookup = empty_lookup(by_email={"avh@dgrd.de": "avanhoorn"})
        g, _, method, _ = self._run(lookup=lookup, name="andre van hoorn", email="avh@dgrd.de", role="committer")
        commit_uri = URIRef("https://github.com/o/r/commit/abc")
        agent = URIRef("https://github.com/avanhoorn")
        assert (commit_uri, PROV.wasAssociatedWith, agent) in g

    def test_by_name_resolved_commit_was_q_associated(self, kieker_commits):
        lookup = empty_lookup(by_name={"andre van hoorn": "avanhoorn"})
        g, _, method, _ = self._run(lookup=lookup, name="andre van hoorn", email="avh@dgrd.de", role="committer")
        commit_uri = URIRef("https://github.com/o/r/commit/abc")
        agent = URIRef("https://github.com/avanhoorn")
        q_assoc = g.value(commit_uri, PROV.qualifiedAssociation)
        assert (commit_uri, PROV.qualifiedAssociation, q_assoc) in g
        assert (q_assoc, PROV.agent, agent) in g

    def test_by_email_resolved_commit_was_q_associated(self, kieker_commits):
        lookup = empty_lookup(by_email={"avh@dgrd.de": "avanhoorn"})
        g, _, method, _ = self._run(lookup=lookup, name="andre van hoorn", email="avh@dgrd.de", role="committer")
        commit_uri = URIRef("https://github.com/o/r/commit/abc")
        agent = URIRef("https://github.com/avanhoorn")
        q_assoc = g.value(commit_uri, PROV.qualifiedAssociation)
        assert (commit_uri, PROV.qualifiedAssociation, q_assoc) in g
        assert (q_assoc, PROV.agent, agent) in g

    @pytest.mark.parametrize("role", ["author", "committer"])
    def test_by_name_resolved_commit_has_role(self, role):
        lookup = empty_lookup(by_name={"andre van hoorn": "avanhoorn"})
        g, _, method, _ = self._run(lookup=lookup, name="andre van hoorn", email="avh@dgrd.de", role=role)
        commit_uri = URIRef("https://github.com/o/r/commit/abc")
        q_assoc = g.value(commit_uri, PROV.qualifiedAssociation)
        assert (q_assoc, PROV.hadRole, G2P[role]) in g

    @pytest.mark.parametrize("role", ["author", "committer"])
    def test_by_email_resolved_commit_has_role(self, role):
        lookup = empty_lookup(by_email={"avh@dgrd.de": "avanhoorn"})
        g, _, method, _ = self._run(lookup=lookup, name="andre van hoorn", email="avh@dgrd.de", role=role)
        commit_uri = URIRef("https://github.com/o/r/commit/abc")
        q_assoc = g.value(commit_uri, PROV.qualifiedAssociation)
        assert (q_assoc, PROV.hadRole, G2P[role]) in g

class TestWebUiSlot:

    def _run(self, role="committer", name="GitHub", email="noreply@github.com"):
        g = Graph()
        unresolved = []
        stats = __import__("collections").defaultdict(int)
        registry = MintRegistry(BASE)
        method = process_slot(g, "https://github.com/o/r/commit/abc",
                              person(name, email, None), role,
                              empty_lookup(), registry, unresolved, stats)
        return g, method

    def test_detects_web_ui(self):
        _, method = self._run()
        assert method == "web-ui"

    def test_synthetic_agent_for_web_uri(self):
        g, _ = self._run()
        assert (URIRef(BASE + WEB_UI_SLUG), RDF.type, PROV.Agent) in g

    def test_web_ui_is_software_agent(self):
        g, _ = self._run()
        assert (URIRef(BASE + WEB_UI_SLUG), RDF.type, PROV.SoftwareAgent) in g

    def test_web_ui_has_committer_role(self):
        g, _ = self._run()
        assert list(g.objects(None, PROV.hadRole)) == [G2P["committer"]]

    def test_github_is_never_minted_as_an_agent(self):
        g, _ = self._run()
        assert (URIRef(BASE + "github"), RDF.type, PROV.Agent) not in g

    def test_users_noreply_address_is_treated_as_agent(self):
        # Must NOT hit the web-UI branch.
        g, method = self._run(name="ghgr", email="ghgr@users.noreply.github.com")
        assert method == "minted"
        assert (URIRef(BASE + "ghgr"), RDF.type, PROV.Agent) in g


class TestResolverCli:

    def _run(self, tmp_path, commits, lookup, extra=()):
        commits_path = tmp_path / "commits.json"
        commits_path.write_text(json.dumps(commits, ensure_ascii=False), encoding="utf-8")
        lookup_path = tmp_path / "lookup.json"
        lookup_path.write_text(json.dumps(lookup, ensure_ascii=False), encoding="utf-8")
        out_ttl = tmp_path / "orphans.ttl"

        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--commits", str(commits_path), "--lookup", str(lookup_path),
             "--output", str(out_ttl), *extra],
            capture_output=True, text=True,
        )
        assert proc.returncode == 0, proc.stderr
        return (proc, out_ttl,
                tmp_path / "orphans_unresolved.json",
                tmp_path / "orphans_review.json")

    def test_writes_parseable_turtle(self, tmp_path, kieker_commits):
        _, out_ttl, _, _ = self._run(tmp_path, kieker_commits, empty_lookup())
        g = Graph()
        g.parse(out_ttl, format="turtle")
        assert len(g) > 0

    def test_only_orphan_commits_appear(self, tmp_path, kieker_commits):
        _, out_ttl, _, _ = self._run(tmp_path, kieker_commits, empty_lookup())
        g = Graph()
        g.parse(out_ttl, format="turtle")
        subjects = {str(s) for s in g.subjects(PROV.qualifiedAssociation, None)}
        assert "https://github.com/kieker-monitoring/kieker/commit/d69b9a01" not in subjects
        assert "https://github.com/kieker-monitoring/kieker/commit/25853fd8" in subjects

    def test_previously_unresolvable_person_is_now_minted(self, tmp_path, kieker_commits):
        # Before minting, "Totally Unknown Person" produced no triples.
        _, out_ttl, unresolved_path, review_path = self._run(tmp_path, kieker_commits, empty_lookup())
        g = Graph()
        g.parse(out_ttl, format="turtle")
        assert (URIRef(BASE + "avantaclue"), RDF.type, PROV.Agent) in g
        assert json.loads(unresolved_path.read_text(encoding="utf-8")) == []

    def test_both_roles_appear(self, tmp_path, kieker_commits):
        _, out_ttl, _, _ = self._run(tmp_path, kieker_commits, empty_lookup())
        g = Graph()
        g.parse(out_ttl, format="turtle")
        triples = list(g.objects(None, PROV.hadRole))
        assert  G2P["committer"] in triples
        assert G2P["author"] in triples



    def test_review_file_lists_minted_agents(self, tmp_path, kieker_commits):
        _, _, _, review_path = self._run(tmp_path, kieker_commits, empty_lookup())
        review = json.loads(review_path.read_text(encoding="utf-8"))
        slugs = {m["slug"] for m in review["minted"]}
        assert "avantaclue" in slugs

    def test_false_merge_is_reported_on_stdout_and_on_disk(self, tmp_path):
        commits = [
            commit("https://x/commit/1", person("Nina Marwede", "nina.marwede@uni-oldenburg.de", None)),
            commit("https://x/commit/2", person("Nina Marwede", "nina.marwede@soton.ac.uk", None)),
        ]
        proc, _, _, review_path = self._run(tmp_path, commits, empty_lookup())
        review = json.loads(review_path.read_text(encoding="utf-8"))

        assert len(review["name_email_conflicts"]) == 1
        assert "false merge" in proc.stdout
        assert "ninamarwede" in proc.stdout

    def test_false_split_is_reported(self, tmp_path):
        commits = [
            commit("https://x/commit/1", person("Nina Marwede", "nina@x.de", None)),
            commit("https://x/commit/2", person("N. Marwede", "nina@x.de", None)),
        ]
        proc, _, _, review_path = self._run(tmp_path, commits, empty_lookup())
        review = json.loads(review_path.read_text(encoding="utf-8"))

        assert len(review["email_name_conflicts"]) == 1
        assert "false split" in proc.stdout

    def test_clean_run_reports_no_disagreements(self, tmp_path):
        commits = [commit("https://x/commit/1", person("Nina Marwede", "nina@x.de", None))]
        proc, _, _, _ = self._run(tmp_path, commits, empty_lookup())
        assert "No name/email disagreements" in proc.stdout

    def test_repeated_agent_is_not_duplicated(self, tmp_path):
        commits = [
            commit("https://x/commit/1", person("Nina Marwede", "nina@x.de", None)),
            commit("https://x/commit/2", person("Nina Marwede", "nina@x.de", None)),
        ]
        _, out_ttl, _, _ = self._run(tmp_path, commits, empty_lookup())
        g = Graph()
        g.parse(out_ttl, format="turtle")
        agent = URIRef(BASE + "ninamarwede")
        assert len(list(g.triples((agent, RDF.type, PROV.Agent)))) == 1

    def test_empty_commits_file(self, tmp_path):
        _, out_ttl, unresolved_path, review_path = self._run(tmp_path, [], empty_lookup())
        g = Graph()
        g.parse(out_ttl, format="turtle")
        assert len(g) == 0
        assert json.loads(unresolved_path.read_text(encoding="utf-8")) == []
        assert json.loads(review_path.read_text(encoding="utf-8"))["minted"] == []
