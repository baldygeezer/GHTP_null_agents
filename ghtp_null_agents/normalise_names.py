
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

def test_is_idempotent(self):
    once = normalise_email("  AVH@X.DE ")
    assert normalise_email(once) == once

def test_leaves_diacritics(self):
    '''we don't want to strip these as messing with ascii here
    could merge emails that are genuinely different'''
    assert normalise_email('doüghǎl@mágic.ròundabout.ac.uk')=='doüghǎl@mágic.ròundabout.ac.uk'