import re

from rdflib import URIRef, Graph, Literal, BNode, Namespace
from rdflib.namespace import RDF, RDFS
from ghtp_null_agents.normalise_names import normalise_name, normalise_email, mint_id_from_name

DEFAULT_AGENT_BASE = "http://soton.ac.uk/pars/agents/"
PROV = Namespace("http://www.w3.org/ns/prov#")
G2P = Namespace("http://purl.org/github2prov/")
SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.\-]*:")

def resolve_agent_uri(identifier):
    # if it's already a complete uri (has a scheme) leave it alone
    if SCHEME_RE.match(identifier):
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


def process_slot(graph: Graph, commit_url: str, person: dict, role: str,
                 lookup: dict, registry: MintRegistry, unresolved: list, stats: dict):
    login, method = resolve_identifier(person.get("name"), person.get("email"), lookup)
    if login:
        uri = resolve_agent_uri(login)
        graph.add((uri, RDF.type, PROV.Agent))
        return method

    slug = mint_id_from_name(person.get("name"))
    uri = registry.mint(slug, person.get("name"), person.get("email"), commit_url, role)
    graph.add((uri, RDF.type, PROV.Agent))
    graph.add((uri, RDFS.label, Literal(person.get("name"))))

    commit_ref = URIRef(commit_url)
    graph.add((commit_ref, PROV.wasAssociatedWith, uri))
    qassoc = BNode()
    graph.add((commit_ref, PROV.qualifiedAssociation, qassoc))
    graph.add((qassoc, PROV.agent, uri))
    graph.add((qassoc, PROV.hadRole, G2P[role]))

    return "minted"



