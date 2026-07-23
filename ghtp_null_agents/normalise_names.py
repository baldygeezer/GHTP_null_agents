
import unicodedata


def normalise_name(raw_name)->str:
    lowered = raw_name.lower().replace("ß", "ss")
    decomposed = unicodedata.normalize("NFKD", lowered)
    return "".join(c for c in decomposed if not unicodedata.combining(c))

