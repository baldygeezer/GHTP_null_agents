




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
