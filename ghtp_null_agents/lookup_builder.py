import argparse
import json
from pathlib import Path

from ghtp_null_agents.normalise_names import normalise_name, normalise_email

COMMITS_PATH=Path('data') / "commits.json"
LOOKUP_PATH=Path('data') / "lookup.json"

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


def _harvest_known_logins(commits):
    known_logins = {}
    for commit in commits:
        for role in ("author", "committer"):
            actor = commit.get("commit", {}).get(role)
            if actor is None:
                continue
            login = extract_login(actor.get("user"))
            if login:
                known_logins.setdefault(normalise_name(login), login)
    return known_logins


def process_commits(commits, builder):
    counts = {"author": 0, "committer": 0}
    known_logins = _harvest_known_logins(commits)

    for commit in commits:
        for role in counts:
            actor = commit.get("commit", {}).get(role)
            if actor is None:
                continue
            login = extract_login(actor.get("user"))
            if not login:
                name = actor.get("name")
                login = known_logins.get(normalise_name(name)) if name else None
            if not login:
                continue
            builder.add(name=actor.get("name"),
                        email=actor.get("email"),
                        login=login,
                        commit_url=commit["url"],
                        role=role)
            counts[role] += 1
    return counts['author'], counts['committer']


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--commits", default=str(COMMITS_PATH))
    parser.add_argument("--lookup", default=str(LOOKUP_PATH))
    parser.add_argument("--conflicts", default=None)
    ns = parser.parse_args()

    commits_path = Path(ns.commits)
    lookup_path = Path(ns.lookup)
    conflicts_path = Path(ns.conflicts) if ns.conflicts else lookup_path.parent / "lookup_conflicts.json"

    commits = json.loads(commits_path.read_text(encoding="utf-8"))
    builder = LookupBuilder()
    process_commits(commits, builder)

    lookup_path.write_text(
        json.dumps({"by_name": builder.by_name, "by_email": builder.by_email}, ensure_ascii=False)
    )

    conflicts = builder.conflicts()
    conflicts_path.write_text(json.dumps(conflicts, ensure_ascii=False))
    if not conflicts:
        print("No conflicts found.")
    else:
        print(f"{len(conflicts)} conflicts found.")


if __name__ == "__main__":
    main()
