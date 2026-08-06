
from rdflib import URIRef


def resolve_agent_uri(identifier):
    if identifier.startswith("mailto:"):
        return URIRef(identifier)
    if "@" in identifier:
        return URIRef(f"mailto:{identifier}")
    return URIRef(f"https://github.com/{identifier}")