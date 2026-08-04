
import re
import unicodedata


def normalise_name(raw_name)->str:
    lowered = raw_name.lower().replace("ß", "ss")
    decomposed = unicodedata.normalize("NFKD", lowered)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    no_periods = stripped.replace(".", "")
    return re.sub(r"\s+", " ", no_periods).strip()


def normalise_email(raw_email)->str:
    if not raw_email:
        return ""
    return raw_email.strip().lower()

def mint_id_from_slug(raw_slug)->str:
    """derive a unique (-ish) id from a github slug, eg a username. punctuation, spaces, numbers and
    diacritics are all stripped and the string is lowercased.
    a string with no usable chars returns an empty string.
    """
    normalised = normalise_name(raw_slug)
    return re.sub(r"[^a-z]", "", normalised)


def mint_id_from_name(raw_name)->str:
    """derive a unique (-ish) id from a name for agents we can't find on github. punctuation, spaces, numbers and
    diacritics are all stripped and the string is lowercased, eg:
      '"Oscar.Martinez.Rubi"',  'Oscar Martinez Rubi' 'Oscar Martiñéz Rubi' are all changed to 'oscarmartinezrubi'
      a string with no usable cars returns §§§§§§an emoty string, eg 1234.3 and 78:0:03 09.8 will all change to ""
      """
    normalised = normalise_name(raw_name)
    return re.sub(r"[^a-z]", "", normalised)