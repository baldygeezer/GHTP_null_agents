from ghtp_null_agents.normalise_names import normalise_name, normalise_email



def extract_login(usr: dict):
    if not isinstance(usr, dict):
        return None
    if usr.get("__typename") == "Bot":
        return None
    return usr.get("login")


class LookupBuilder:
    def __init__(self):
        self.by_name = {}
        self.by_email = {}
        self._name_logins_seen = {}
        self._email_logins_seen = {}
        self._name_occurrences = {}

    def add(self, name, email, login, commit_url, role):
        if name and normalise_name(name):
            key = normalise_name(name)
            self.by_name.setdefault(key, login)
            self._name_logins_seen.setdefault(key, []).append(login)
            self._name_occurrences.setdefault(key, []).append(
                {"commit_url": commit_url, "role": role, "raw_value": name}
            )
        if email:
            key = normalise_email(email)
            self.by_email[key] = login
            self._email_logins_seen.setdefault(key, []).append(login)

    def conflicts(self):
        name_conflicts = [
            {
                "field": "name",
                "normalized_key": key,
                "logins_seen": logins,
                "occurrences": self._name_occurrences[key],
            }
            for key, logins in self._name_logins_seen.items()
            if len(set(logins)) > 1
        ]
        email_conflicts = [
            {"field": "email", "normalized_key": key, "logins_seen": logins}
            for key, logins in self._email_logins_seen.items()
            if len(set(logins)) > 1
        ]
        return name_conflicts + email_conflicts


def process_commits(commits, builder):
    n_author = 0
    n_committer = 0
    for commit in commits:
        for role in ("author", "committer"):
            actor = commit["commit"][role]
            login = extract_login(actor.get("user"))
            if not login:
                continue
            builder.add(actor.get("name"), actor.get("email"), login, commit["url"], role)
            if role == "author":
                n_author += 1
            else:
                n_committer += 1
    return n_author, n_committer