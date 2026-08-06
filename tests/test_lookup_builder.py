import inspect
import json
import subprocess
import sys
from pathlib import Path

import pytest

from ghtp_null_agents.lookup_builder import extract_login, LookupBuilder, process_commits, COMMITS_PATH, LOOKUP_PATH
from tests.fixtures import user_json, commit, person, kieker_commits



class TestExtractLogin:

    def test_graphql_user_object(self):
        assert extract_login(user_json("avanhoorn")) == "avanhoorn"

    @pytest.mark.parametrize("login", [
        ("avanhoorn"),
        ("baldygeezer"), ])
    def test_plain_login_string_is_rejected(self, login):
        # we should see logins being checked. If we do something is wrong, and we don't want to be assigning a login to
        # anything so it should return none
        assert extract_login(login) is None

    @pytest.mark.parametrize("falsy", [None, {}, "", False])
    def test_unresolved_returns_none(self, falsy):
        assert extract_login(falsy) is None

    @pytest.mark.parametrize("login", [user_json("dependabot", typename="Bot"),
                                       user_json("myclevercithing", typename="Bot")])
    def test_bot_is_skipped(self, login):
        # Mapping a human name onto a bot login would poison the lookup.
        assert extract_login(login) is None

    def test_preserves_login_case(self):
        # github2prov treats logins as case-sensitive.
        assert extract_login(user_json("ChristianWulf")) == "ChristianWulf"


class TestLookupBuilder:
    def test_records_name_and_email(self):
        b = LookupBuilder()
        b.add("André van Hoorn", "AVH@X.de", "avanhoorn", "commit_id", "author")
        assert b.by_name == {"andre van hoorn": "avanhoorn"}
        assert b.by_email == {"avh@x.de": "avanhoorn"}

    def test_login_case_is_preserved_in_values(self):
        # ... because now we are matching - we don't want case in emails to break a match, and github2prov treats github
        # user slugs as case-sensitive
        b = LookupBuilder()
        b.add("christian wulf", "cw@x.de", "ChristianWulf", "commit_id", "author")
        assert b.by_name["christian wulf"] == "ChristianWulf"

    def test_missing_name_still_records_email(self):
        b = LookupBuilder()
        b.add(None, "only@email.de", "someone", "commit_id", "author")
        assert b.by_name == {}
        assert b.by_email == {"only@email.de": "someone"}

    def test_missing_email_still_records_name(self):
        b = LookupBuilder()
        b.add("Only Name", None, "someone", "commit_id", "author")
        assert b.by_name == {"only name": "someone"}
        assert b.by_email == {}

    def test_blank_name_is_not_recorded_as_empty_key(self):
        b = LookupBuilder()
        b.add("   ", "x@y.de", "someone", "commit_id", "author")
        assert "" not in b.by_name

    def test_first_seen_login_wins_in_the_table(self):
        b = LookupBuilder()
        b.add("Ambiguous Name", None, "first-login", "commit_id", "author")
        b.add("Ambiguous Name", None, "second-login", "commit_id", "author")
        b.add("brian", None, "another_login", "commit_id", "author")
        b.add("Ambiguous Name", None, "third-login", "commit_id", "author")
        assert b.by_name["ambiguous name"] == "first-login"
        assert b.by_name["brian"] == "another_login"

    def test_conflicting_name_is_reported(self):
        b = LookupBuilder()
        b.add("Ambiguous Name", None, "first-login", "commit_id", "author")
        b.add("Ambiguous Name", None, "second-login", "commit_id", "committer")

        conflicts = b.conflicts()
        assert len(conflicts) == 1
        c = conflicts[0]
        assert c["field"] == "name"
        assert c["normalized_key"] == "ambiguous name"
        assert c["logins_seen"] == ["first-login", "second-login"]

    def test_conflicting_email_is_reported(self):
        b = LookupBuilder()
        b.add(None, "shared@x.de", "login-one", "commit_id", "author")
        b.add(None, "SHARED@X.de", "login-two", "commit_id", "committer")

        conflicts = b.conflicts()
        assert len(conflicts) == 1
        assert conflicts[0]["field"] == "email"
        assert conflicts[0]["normalized_key"] == "shared@x.de"

    def test_two_names_sharing_one_login_is_not_a_conflict(self):
        # normal: one person commits under several spellings.
        b = LookupBuilder()
        b.add("Nils Ehmke", None, "nils-christian", "commit_id", "author")
        b.add("Nils Christian Ehmke", None, "nils-christian", "commit_id", "author")
        assert b.conflicts() == []
        assert len(b.by_name) == 2

    def test_conflict_carries_full_info(self):
        # we need the commit url, role + raw spelling to resolve these by hand.
        b = LookupBuilder()
        b.add("Ambiguous Name", None, "first-login", "commit-a", "author")
        b.add("ambiguous  name", None, "second-login", "commit-b", "committer")

        occs = b.conflicts()[0]["occurrences"]
        assert {o["commit_url"] for o in occs} == {"commit-a", "commit-b"}
        assert {o["role"] for o in occs} == {"author", "committer"}
        assert {o["raw_value"] for o in occs} == {"Ambiguous Name", "ambiguous  name"}

    def test_add_has_no_optional_params(self):
        signature = inspect.signature(LookupBuilder.add)
        for name, param in signature.parameters.items():
            # fail if any parameter has default value
            assert param.default is inspect.Parameter.empty, (
                f"Parameter '{name}' is optional because it has a default value: {param.default}"
            )
            # fail if it accepts variable positional arguments (*args)
            assert param.kind is not inspect.Parameter.VAR_POSITIONAL, (
                f"Parameter '{name}' (*args) makes arguments optional."
            )

            # fail if it accepts variable keyword arguments (**kwargs)
            assert param.kind is not inspect.Parameter.VAR_KEYWORD, (
                f"Parameter '{name}' (**kwargs) makes arguments optional."
            )

    def test_repeated_consistent_mapping_is_not_a_conflict(self):
        b = LookupBuilder()
        b.add("Andre van Hoorn", "avh@x.de", "avanhoorn", "u1", "author")
        b.add("André van Hoorn", "AVH@X.de", "avanhoorn", "u2", "committer")
        assert b.conflicts() == []
        assert b.by_name == {"andre van hoorn": "avanhoorn"}


class TestProcessCommits:

    def test_harvests_resolved_author_and_committer(self):
        b = LookupBuilder()
        commits = [commit("u1", person("Andre van Hoorn", "avh@x.de", user_json("avanhoorn")))]
        n_author, n_committer = process_commits(commits, b)
        assert (n_author, n_committer) == (1, 1)
        assert b.by_name["andre van hoorn"] == "avanhoorn"

    def test_skips_null_users(self):
        b = LookupBuilder()
        commits = [commit("u1", person("Orphan Person", "o@x.de", None))]
        assert process_commits(commits, b) == (0, 0)
        assert b.by_name == {}

    def test_skips_commits_with_no_user_key_at_all(self):
        # ...in repos that never went through the resolution step.
        b = LookupBuilder()
        commits = [commit("u1", person("Someone", "s@x.de"), omit_user_key=True)]
        assert process_commits(commits, b) == (0, 0)

    c1 = [commit("u1", author=person("Author McAuthorface", "a@x.de", user_json("authorface")),
                 committer=person("Committer McCommitterface", "c@x.de", None),
                 )]
    c2 = [commit("u1", author=person("Author McAuthorface", "a@x.de", user_json("authorface")),
                 committer=person("Committer McCommitterface", "c@x.de", user_json("committerface")),
                 )]
    c3 = [commit("u1", author=person("Author McAuthorface", "a@x.de", user_json("authorface")),
                 committer=person("Committer McCommitterface", "c@x.de", user_json("committerface")),
                 ),
          commit("u2", author=person("Author McAuthorface", "a@x.de", user_json("authorface")),
                 committer=person("Committer McCommitterface", "c@x.de", None),
                 )
          ]

    @pytest.mark.parametrize("commits, expected", [(c1, (1, 0)),
                                                   (c2, (1, 1)),
                                                   (c3, (2, 1))
                                                   ])
    def test_counts_author_and_committer_independently(self, commits, expected):
        b = LookupBuilder()
        assert process_commits(commits, b) == expected

    def test_handle_missing_commit_block(self):
        b = LookupBuilder()
        assert process_commits([{"url": "u1"}], b) == (0, 0)

    def test_handles_null_author_block(self):
        b = LookupBuilder()
        assert process_commits([{"url": "u1", "commit": {"author": None, "committer": None}}], b) == (0, 0)

SCRIPT = Path(__file__).resolve().parent.parent / "ghtp_null_agents" / "lookup_builder.py"

@pytest.mark.usefixtures("kieker_commits")
class TestBuilderCli:

    def _run(self, tmp_path, commits):
        commits_path = tmp_path / "commits.json"
        commits_path.write_text(json.dumps(commits, ensure_ascii=False), encoding="utf-8")
        lookup_path = tmp_path / "lookup.json"

        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--commits", str(commits_path), "--lookup", str(lookup_path)],
            capture_output=True, text=True,
        )
        assert proc.returncode == 0, proc.stderr
        return proc, lookup_path, tmp_path / "lookup_conflicts.json"

    def test_writes_lookup_file(self, tmp_path, kieker_commits):
        proc, lookup_path, conflicts_path = self._run(tmp_path, kieker_commits)
        assert lookup_path.exists()

    def test_writes_conflicts_file(self, tmp_path, kieker_commits):
        proc, lookup_path, conflicts_path = self._run(tmp_path, kieker_commits)
        assert conflicts_path.exists()

    def test_lookup_keys(self, tmp_path, kieker_commits):
        proc, lookup_path, conflicts_path = self._run(tmp_path, kieker_commits)
        lookup = json.loads(lookup_path.read_text(encoding="utf-8"))
        assert set(lookup) == {"by_name", "by_email"}

    def test_looks_up_by_name(self, tmp_path, kieker_commits):
        proc, lookup_path, conflicts_path = self._run(tmp_path, kieker_commits)
        lookup = json.loads(lookup_path.read_text(encoding="utf-8"))
        assert lookup["by_name"]["andre van hoorn"] == "avanhoorn"

    def test_looks_up_by_email(self, tmp_path, kieker_commits):
        proc, lookup_path, conflicts_path = self._run(tmp_path, kieker_commits)
        lookup = json.loads(lookup_path.read_text(encoding="utf-8"))
        assert lookup["by_email"]["nie@informatik.uni-kiel.de"] == "nils-christian"

    def test_clean_run_reports_no_conflicts(self, tmp_path, kieker_commits):
        proc, _, conflicts_path = self._run(tmp_path, kieker_commits)
        assert "No conflicts found." in proc.stdout
        assert json.loads(conflicts_path.read_text(encoding="utf-8")) == []


    def test_conflicts_are_reported_on_disc(self, tmp_path):
        commits = [
            commit("u1", person("Ambiguous Name", "amb@x.de", user_json("login-one"))),
            commit("u2", person("Ambiguous Name", "amb@x.de", user_json("login-two"))),
        ]
        proc, _, conflicts_path = self._run(tmp_path, commits)

        conflicts = json.loads(conflicts_path.read_text(encoding="utf-8"))
        assert len(conflicts) == 2  # one for the name, one for the email

    def test_conflicts_are_reported_on_stdout(self, tmp_path):
        commits = [
            commit("u1", person("Ambiguous Name", "amb@x.de", user_json("login-one"))),
            commit("u2", person("Ambiguous Name", "amb@x.de", user_json("login-two"))),
        ]
        proc, _, conflicts_path = self._run(tmp_path, commits)
        assert "conflict" in proc.stdout.lower()

    def test_conflicts_flag(self, tmp_path, kieker_commits):
        commits_path = tmp_path / "commits.json"
        commits_path.write_text(json.dumps(kieker_commits, ensure_ascii=False), encoding="utf-8")
        custom = tmp_path / "my_conflicts.json"

        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--commits", str(commits_path),
             "--lookup", str(tmp_path / "lookup.json"), "--conflicts", str(custom)],
            capture_output=True, text=True,
        )
        assert proc.returncode == 0, proc.stderr
        assert custom.exists()

    def test_conflicts_location_flag(self, tmp_path, kieker_commits):
        commits_path = tmp_path / "commits.json"
        commits_path.write_text(json.dumps(kieker_commits, ensure_ascii=False), encoding="utf-8")
        custom = tmp_path / "my_conflicts.json"

        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--commits", str(commits_path),
             "--lookup", str(tmp_path / "lookup.json"), "--conflicts", str(custom)],
            capture_output=True, text=True,
        )
        assert proc.returncode == 0, proc.stderr
        assert custom.exists()

    def test_output_json_is_utf8_not_escaped(self, tmp_path):
        # ensure_ascii=False keeps the report readable when you open it to
        # resolve names by hand.
        commits = [
            commit("u1", person("Jürgen Walter", "jw@x.de", user_json("login-one"))),
            commit("u2", person("Jürgen Walter", "jw@x.de", user_json("login-two"))),
        ]
        _, _, conflicts_path = self._run(tmp_path, commits)
        assert "Jürgen" in conflicts_path.read_text(encoding="utf-8")


    def test_commits_location_has_default(self, tmp_path, kieker_commits):
        commits_path = tmp_path / COMMITS_PATH
        commits = [
            commit("u1", person("Hugh Jars", "h.jars@x.de", user_json("login-one"))),
            commit("u2", person("Chris Peacock", "CPK@x.de", user_json("login-two"))),
        ]
        commits_path.parent.mkdir(parents=True, exist_ok=True)
        commits_path.write_text(json.dumps(commits, ensure_ascii=False), encoding="utf-8")
        custom = tmp_path / "my_conflicts.json"

        proc = subprocess.run(
            [sys.executable, str(SCRIPT),
             "--lookup", str(tmp_path / "lookup.json"), "--conflicts", str(custom)],
            capture_output=True, text=True, cwd=tmp_path,
        )
        assert proc.returncode == 0, proc.stderr
        assert "chris peacock" in Path(tmp_path / "lookup.json").read_text(encoding="utf-8")


    def test_lookup_location_has_default(self, tmp_path, kieker_commits):
        commits_path = tmp_path / COMMITS_PATH
        commits = [
            commit("u1", person("William Ellard", "w.ellerd@x.de", user_json("login-one"))),
            commit("u2", person("Chris Peacock", "CPK@x.de", user_json("login-two"))),
        ]
        commits_path.parent.mkdir(parents=True, exist_ok=True)
        commits_path.write_text(json.dumps(commits, ensure_ascii=False), encoding="utf-8")
        custom = tmp_path / "my_conflicts.json"

        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--commits", str(commits_path), "--conflicts", str(custom)],
            capture_output=True, text=True, cwd=tmp_path,
        )
        assert proc.returncode == 0, proc.stderr
        assert "william ellard" in Path(tmp_path / LOOKUP_PATH).read_text(encoding="utf-8")