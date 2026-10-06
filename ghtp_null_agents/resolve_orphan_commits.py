import argparse
import json
import re
import sys
from pathlib import Path

from rdflib import URIRef, Graph, Literal, BNode, Namespace
from rdflib.namespace import RDF, RDFS

from ghtp_null_agents.lookup_builder import COMMITS_PATH, LOOKUP_PATH, LookupBuilder, process_commits
from ghtp_null_agents.normalise_names import normalise_name, normalise_email, mint_id_from_name

DEFAULT_AGENT_BASE = "http://soton.ac.uk/pars/agents/"
PROV = Namespace("http://www.w3.org/ns/prov#")
G2P = Namespace("http://purl.org/github2prov/")
SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.\-]*:")

# github web UI committer identity
WEB_UI_EMAIL = "noreply@github.com"
WEB_UI_SLUG = "github-web-ui"
WEB_UI_LABEL = "GitHub (web UI)"

OUTPUT_PATH=Path('data') / "orphans.ttl"

NOREPLY_ID_RE = re.compile(r"^(\d+)\+.+@users\.noreply\.github\.com$", re.IGNORECASE)
IDENTITY_MAP_PATH = Path("data") / "identity_map.json"   # module level

def noreply_account_id(email):
    m = NOREPLY_ID_RE.match((email or "").strip())
    return m.group(1) if m else None


def resolve_agent_uri(identifier):
    # if it's already a complete uri (has a scheme) leave it alone
    if SCHEME_RE.match(identifier):
        return URIRef(identifier)
    # if it's a bare email address make it into a mailto:
    if "@" in identifier:
        return URIRef(f"mailto:{identifier}")
    # otherise it's a github user
    return URIRef(f"https://github.com/{identifier}")


def resolve_identifier(name, email, lookup, identity_map):
    # if we can get a corpus-wide github id resolution from numeric in no reply than that is canonical
    acct_id = noreply_account_id(email)
    if acct_id and acct_id in identity_map["by_id"]:
        return identity_map["by_id"][acct_id], "cross-repo-id"
    # otherwise use email from corpus
    email_key = normalise_email(email)
    if email_key and email_key in identity_map["by_email"]:
        return identity_map["by_email"][email_key], "cross-repo-email"

    # resolve within repo
    if name:
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
                "names": sorted(names),
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
                 lookup: dict,indentity_map: dict, registry: MintRegistry, unresolved: list, stats: dict):
    if not person.get("name") and not person.get("email"):
        unresolved.append({
            "name": person.get("name"),
            "email": person.get("email"),
            "commit_url": commit_url,
            "role": role,
            "reason": "no name or email",
        })
        return None
    # the web UI branch this commit wass made using a web browswr
    if person.get("email") == WEB_UI_EMAIL:
        uri = URIRef(DEFAULT_AGENT_BASE + WEB_UI_SLUG)
        graph.add((uri, RDF.type, PROV.Agent))
        # we treat the web ui as a software agent
        graph.add((uri, RDF.type, PROV.SoftwareAgent))

        commit_ref = URIRef(commit_url)
        graph.add((commit_ref, PROV.wasAssociatedWith, uri))
        qassoc = BNode()
        graph.add((commit_ref, PROV.qualifiedAssociation, qassoc))
        graph.add((qassoc, PROV.agent, uri))
        graph.add((qassoc, PROV.hadRole, G2P[role]))

        return "web-ui"

    login, method = resolve_identifier(person.get("name"), person.get("email"), lookup, indentity_map)
    # this is the lookup hit branch - we found a github login - whoopeee!
    if login:
        uri = resolve_agent_uri(login)
        graph.add((uri, RDF.type, PROV.Agent))
        commit_ref = URIRef(commit_url)
        graph.add((commit_ref, PROV.wasAssociatedWith, uri))
        qassoc = BNode()
        graph.add((commit_ref, PROV.qualifiedAssociation, qassoc))
        graph.add((qassoc, PROV.agent, uri))
        graph.add((qassoc, PROV.hadRole, G2P[role]))
        return method
    # here be dragons - if we get here then there's no match, so we make unique if for the Agent
    slug = mint_id_from_name(person.get("name")) if person.get("name") else ""
    # first, if we can't make a slug from the name...
    if not slug:
        unresolved.append({
            "name": person.get("name"),
            "email": person.get("email"),
            "commit_url": commit_url,
            "role": role,
            "reason": "name has no slug-able characters",
        })
        # ...then lets just give up
        return None
    # otherwise make some gubbins @todo the code that makes the assocations is being dupliacted so needs extracting into a function
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


def parse_args(args) ->argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--commits", default=None)
    parser.add_argument("--lookup", default=None)
    parser.add_argument("--output", default=None)
    parser.add_argument("--folder", default=None)
    ns = parser.parse_args(args)

    if ns.folder is not None and (ns.commits is not None or ns.lookup is not None or ns.output is not None):
        raise ValueError("--folder cannot be combined with --commits, --lookup, or --output")

    if ns.commits is None:
        ns.commits = str(COMMITS_PATH)
    if ns.lookup is None:
        ns.lookup = str(LOOKUP_PATH)
    if ns.output is None:
        ns.output = str(OUTPUT_PATH)

    return ns


def _get_repo_subfolder(ns: argparse.Namespace) -> Path:
    return next(p for p in Path(ns.folder).iterdir() if p.is_dir())

def get_commits_path(ns: argparse.Namespace) -> Path:
    if ns.folder is not None:
        return _get_repo_subfolder(ns) / "commits.json"
    return Path(ns.commits)

def get_lookup_path(ns: argparse.Namespace) -> Path:
    if ns.folder is not None:
        return _get_repo_subfolder(ns) / "lookup.json"
    return Path(ns.lookup)

def get_output_path(ns: argparse.Namespace) -> Path:
    if ns.folder is not None:
        subfolder = _get_repo_subfolder(ns)
        return subfolder / f"{subfolder.name}.ttl"
    return Path(ns.output)



def process_repo(commits_path: Path, lookup_path: Path, output_path: Path):
    commits = json.loads(commits_path.read_text(encoding="utf-8"))

    if not lookup_path.exists():
        builder = LookupBuilder()
        process_commits(commits, builder)
        lookup = {"by_name": builder.by_name, "by_email": builder.by_email}
        lookup_path.write_text(json.dumps(lookup, ensure_ascii=False))
    else:
        lookup = json.loads(lookup_path.read_text(encoding="utf-8"))

    identity_map = (json.loads(IDENTITY_MAP_PATH.read_text(encoding="utf-8"))
                  if IDENTITY_MAP_PATH.exists()
                  else {"by_id": {}, "by_email": {}})

    graph = Graph()
    registry = MintRegistry(DEFAULT_AGENT_BASE)
    unresolved = []
    stats = {}

    for c in commits:
        for role in ("author", "committer"):
            slot = c["commit"][role]
            if slot.get("user") is None:
                process_slot(graph, c["url"], slot, role, lookup,identity_map, registry, unresolved, stats)

    output_path.write_text(graph.serialize(format="turtle"))

    unresolved_path = output_path.parent / f"{output_path.stem}_unresolved.json"
    unresolved_path.write_text(json.dumps(unresolved, ensure_ascii=False))

    review = registry.review()
    review_path = output_path.parent / f"{output_path.stem}_review.json"
    review_path.write_text(json.dumps(review, ensure_ascii=False))

    if review["name_email_conflicts"]:
        slugs = ", ".join(c["slug"] for c in review["name_email_conflicts"])
        print(f"{len(review['name_email_conflicts'])} possible false merge(s): {slugs} — see {review_path}")

    if review["email_name_conflicts"]:
        emails = ", ".join(c["email"] for c in review["email_name_conflicts"])
        print(f"{len(review['email_name_conflicts'])} possible false split(s): {emails} — see {review_path}")

    if not review["name_email_conflicts"] and not review["email_name_conflicts"]:
        print("No name/email disagreements found.")


def main():
    ns = parse_args(sys.argv[1:])

    if ns.folder is not None:
        for subfolder in sorted(p for p in Path(ns.folder).iterdir() if p.is_dir()):
            commits_path = subfolder / "commits.json"
            if not commits_path.exists():
                continue
            lookup_path = subfolder / "lookup.json"
            output_path = subfolder / f"{subfolder.name}.ttl"
            process_repo(commits_path, lookup_path, output_path)
    else:
        process_repo(get_commits_path(ns), get_lookup_path(ns), get_output_path(ns))




if __name__ == "__main__":
    main()

