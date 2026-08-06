
from rdflib import URIRef
DEFAULT_AGENT_BASE = "http://soton.ac.uk/pars/agents/"

def resolve_agent_uri(identifier):
    if identifier.startswith("mailto:"):
        return URIRef(identifier)
    if "@" in identifier:
        return URIRef(f"mailto:{identifier}")
    return URIRef(f"https://github.com/{identifier}")