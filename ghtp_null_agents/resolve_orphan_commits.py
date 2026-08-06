
from rdflib import URIRef, Graph

from ghtp_null_agents.normalise_names import normalise_name, normalise_email

DEFAULT_AGENT_BASE = "http://soton.ac.uk/pars/agents/"

def resolve_agent_uri(identifier):
    # if it's already a complete url leave it alone
    for scheme in ["https://", "http://", "mailto:"]:
        if identifier.startswith(scheme):
            return URIRef(identifier)
    # if it's a bare email address make it into a mailto:
    if "@" in identifier:
        return URIRef(f"mailto:{identifier}")
    # otherise it's a github user
    return URIRef(f"https://github.com/{identifier}")


def resolve_identifier(name, email, lookup):
    name_key = normalise_name(name)
    if name_key in lookup["by_name"]:
        return lookup["by_name"][name_key], "lookup-name"

    email_key = normalise_email(email)
    if email_key in lookup["by_email"]:
        return lookup["by_email"][email_key], "lookup-email"

    return None, None

class MintRegistry:
    """
    Tracks every agent URI minted from a name, so that name/email
    disagreements can be surfaced for manual review afterwards.
    """

    def __init__(self, base):
        self.base = base
        self._occurrences = {}

    def mint(self, slug, name, email, commit_url, role):
        self._occurrences.setdefault(slug, []).append(
            {"name": name, "email": email, "commit_url": commit_url, "role": role}
        )
        return URIRef(self.base + slug)

    def review(self):
        minted = [
            {
                "slug": slug,
                "slots": len(occurrences),
                "names": sorted({o["name"] for o in occurrences}),
            }
            for slug, occurrences in self._occurrences.items()
        ]

        name_email_conflicts = [
            {
                "slug": slug,
                "occurrences": occurrences,
                "emails": sorted({o["email"] for o in occurrences if o["email"]}),
                "uri": self.base + slug,
            }
            for slug, occurrences in self._occurrences.items()
            if len({(o["name"], normalise_email(o["email"])) for o in occurrences if o["email"]}) > 1
        ]

        email_names = {}
        email_slugs = {}
        for slug, occurrences in self._occurrences.items():
            for o in occurrences:
                if not o["email"]:
                    continue
                key = normalise_email(o["email"])
                email_names.setdefault(key, set()).add(o["name"])
                email_slugs.setdefault(key, set()).add(slug)
        email_name_conflicts = [
            {
                "email": email,
                "names": names,
                "slugs": sorted(email_slugs[email]),
                "uris": [self.base + slug for slug in sorted(email_slugs[email])],
            }
            for email, names in email_names.items()
            if len(names) > 1
        ]

        return {
            "minted": minted,
            "name_email_conflicts": name_email_conflicts,
            "email_name_conflicts": email_name_conflicts,
        }


def process_slot(g: Graph, commit_url: str, person: dict, role: str,
                 lookup: dict, registry: MintRegistry, unresolved: list, stats: dict):
    pass