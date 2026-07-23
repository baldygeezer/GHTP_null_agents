
import re
import unicodedata


def normalise_name(raw_name)->str:
    lowered = raw_name.lower().replace("ß", "ss")
    decomposed = unicodedata.normalize("NFKD", lowered)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    no_periods = stripped.replace(".", "")
    return re.sub(r"\s+", " ", no_periods).strip()

