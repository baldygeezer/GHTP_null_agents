
from rdflib import URIRef


def resolve_agent_uri(identifier):
    return URIRef(f"https://github.com/{identifier}")