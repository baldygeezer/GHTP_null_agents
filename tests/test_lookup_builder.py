from ghtp_null_agents.lookup_builder import extract_login, LookupBuilder, process_commits
from tests.fixtures import user_json, commit, person

import pytest

import inspect


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






    c1=[commit("u1",author=person("Author McAuthorface", "a@x.de", user_json("authorface")),
                    committer=person("Committer McCommitterface", "c@x.de", None),
        )]
    c2=[commit("u1",author=person("Author McAuthorface", "a@x.de", user_json("authorface")),
                    committer=person("Committer McCommitterface", "c@x.de", user_json("committerface")),
        )]
    c3=[commit("u1",author=person("Author McAuthorface", "a@x.de", user_json("authorface")),
                    committer=person("Committer McCommitterface", "c@x.de", user_json("committerface")),
        ),
        commit("u2", author=person("Author McAuthorface", "a@x.de", user_json("authorface")),
               committer=person("Committer McCommitterface", "c@x.de", None),
               )
        ]

    @pytest.mark.parametrize("commits, expected",[(c1,(1,0)),
                                                   (c2, (1, 1)),
                                                   (c3, (2, 1))
                                                  ])
    def test_counts_author_and_committer_independently(self, commits, expected):
        b = LookupBuilder()
        assert process_commits(commits, b) == expected

    def test_handle_missing_commit_block(self):
        b = LookupBuilder()
        assert process_commits([{"url": "u1"}], b) == (0, 0)



