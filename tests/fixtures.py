




def user_obj(login, typename="User"):
    """A resolved GraphQL-shaped user object, as in real graphql responses."""
    return {
        "url": f"https://github.com/{login}",
        "login": login,
        "__typename": typename,
    }