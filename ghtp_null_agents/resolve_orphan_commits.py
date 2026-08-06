
from rdflib import URIRef
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