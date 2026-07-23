
import unicodedata


def normalise_name(raw_name)->str:
    decomposed = unicodedata.normalize("NFKD", raw_name.lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))

