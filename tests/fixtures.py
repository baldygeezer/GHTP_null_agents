import pytest


def user_json(login, typename="User"):
    """A resolved GraphQL-shaped user object, as in real graphql responses."""
    return {
        "url": f"https://github.com/{login}",
        "login": login,
        "__typename": typename,
    }


def person(name=None, email=None, user=None, date="2014-02-12T16:25:38Z"):
    """an author/committer block."""
    p = {"date": date}
    if name is not None:
        p["name"] = name
    if email is not None:
        p["email"] = email
    p["user"] = user
    return p


def commit(url, author=None, committer=None, message="msg", omit_user_key=False):
    """
    A full commits.json entry. If `committer` is omitted it mirrors the
    author, which is what most real commit records do.

    omit_user_key=True strips the "user" key entirely (rather than setting
    it to null) -- the shape seen in commits.json files from repos that
    never went through the user-resolution step at all.
    """
    if committer is None:
        committer = dict(author) if author else None

    def _strip(p):
        if p is None:
            return {}
        p = dict(p)
        if omit_user_key:
            p.pop("user", None)
        return p

    return {
        "url": url,
        "sha": url.rsplit("/", 1)[-1],
        "commit": {
            "author": _strip(author),
            "committer": _strip(committer),
            "message": message,
        },
    }


@pytest.fixture
def kieker_commits():
    """
    A  representative slice of data from the kieker repo:
      - a fully resolved commit (avanhoorn)
      - an orphan whose NAME matches the resolved one only after
        diacritic normalisation ("André" vs "Andre")
      - an orphan resolvable only via EMAIL (different name spelling)
      - the resolved commit that makes the above email resolution possible
      - a genuinely unresolvable orphan
      -
    """
    return [
        commit(
            "https://github.com/kieker-monitoring/kieker/commit/d69b9a01",
            person("Andre van Hoorn", "van.hoorn@informatik.uni-stuttgart.de", user_json("avanhoorn")),
            message="fixed javadoc",
        ),
        commit(
            "https://github.com/kieker-monitoring/kieker/commit/25853fd8",
            person("André van Hoorn", "avh@informatik.uni-kiel.de", None),
            message="refactoring",
        ),
        commit(
            "https://github.com/kieker-monitoring/kieker/commit/zzz999",
            person("Nils Ehmke", "nie@informatik.uni-kiel.de", user_json("nils-christian")),
            message="resolved, one name spelling",
        ),
        commit(
            "https://github.com/kieker-monitoring/kieker/commit/78656f09",
            person("Nils Christian Ehmke", "nie@informatik.uni-kiel.de", None),
            message="orphan, different name spelling, same email",
        ),
        commit(
            "https://github.com/kieker-monitoring/kieker/commit/unknown1",
            person("Avan Taclue ", "tup@nowhere.de", None),
            message="unresolvable",
        ),
        commit(
            "https://github.com/kieker-monitoring/kieker/commit/654321",
            author=person("Author McAuthorface", "ama@authorland.de", None),
            committer=person("Committer McCommitterface", "cmc@committerrland.de", None),
            message="this involved two people, an author and a commiter",
        ),
    ]
@pytest.fixture
def other_commits():
    """
    another set for sanity
      -
    """
    return [
        commit(
            "https://github.com/gallifrey/tardis_ctrl/commit/d4b9a47c01",
            person("Frodo Bloggs", "f.bloggs@informatik.uni-stuttgart.de", user_json("bloggs")),
            message="fixed javadoc",
        ),
        commit(
            "https://github.com/gallifrey/tardis_ctrl/commit/e5h53fd8",
            person("Frödo Bloggs", "fb@informatik.uni-kiel.de", None),
            message="refactoring",
        ),
        commit(
            "https://github.com/gallifrey/tardis_ctrl/commit/z339h9",
            person("Ada Lovelace", "ada@informatik.uni-kiel.de", user_json("ada")),
            message="resolved, one name spelling",
        ),
        commit(
            "https://github.com/gallifrey/tardis_ctrl/commit/786bb5x09",
            person("Ada e Lovelace", "ada@informatik.uni-kiel.de", None),
            message="orphan, different name spelling, same email",
        ),
        commit(
            "https://github.com/gallifrey/tardis_ctrl/commit/unknown1",
            person("Ivan OIdea", "eh@nowhere.de", None),
            message="unresolvable",
        ),
        commit(
            "https://github.com/gallifrey/tardis_ctrl/commit/65x3t61",
            author=person("Author McAuthorface", "ama@authorland.de", None),
            committer=person("Committer McCommitterface", "cmc@committerrland.de", None),
            message="this involved two people, an author and a commiter",
        ),
        commit(
            "https://github.com/gallifrey/tardis_ctrl/commit/65x3t741",
            person("Author McAuthorface", "ama1@authorland.de", user_json("authorface")),
            message="resolve the author on name",
        ),
        commit(
            "https://github.com/gallifrey/tardis_ctrl/commit/6f53t61",
            person("Committer a McCommitterface", "cmc@committerrland.de", user_json("committerface")),
            message="resolve committer on email",
        ),
    ]