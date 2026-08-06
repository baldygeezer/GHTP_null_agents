
from rdflib import URIRef

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

