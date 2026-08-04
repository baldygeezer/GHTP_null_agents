import pytest
from ghtp_null_agents.normalise_names import normalise_name, normalise_email, mint_id_from_slug, mint_id_from_name


class TestNormaliseName:

    @pytest.mark.parametrize("raw,expected", [
        ("Andre van Hoorn", "andre van hoorn"),
        ("ANDRE VAN HOORN", "andre van hoorn"),
        ("andre van hoorn", "andre van hoorn"),
        ("AnDrE VaN hOoRn", "andre van hoorn"),
    ])
    def test_fixes_case(self, raw, expected):
        assert normalise_name(raw) == expected

    @pytest.mark.parametrize("raw,expected", [
        ("André van Hoorn", "andre van hoorn"),
        ("Armin Möbius", "armin mobius"),
        ("Marius Löwe", "marius lowe"),
        ("Jürgen Walter", "jurgen walter"),
        ("Dušan Okanović", "dusan okanovic"),
        ("Sören Henning", "soren henning"),
    ])
    def test_fixes_diacritics(self, raw, expected):
        assert normalise_name(raw) == expected

    # uppercase as well!
    @pytest.mark.parametrize("raw,expected", [
        ("bjorn weißenfels","bjorn weissenfels"),
        ("bjorn WEIẞENFELS", "bjorn weissenfels"),
    ])
    def test_fix_eszet(self, raw, expected):
        assert normalise_name(raw) == expected

    @pytest.mark.parametrize("raw,expected", [
        ("John W Smith", "john w smith"),
        ("Karen j Harding", "karen j harding"),
        ("Hugh J Nus", "hugh j nus"),
    ])
    def test_initials_not_stripped(self, raw, expected):
        assert normalise_name(raw) == expected

    @pytest.mark.parametrize("raw,expected", [
        ("john w. smith", "john w smith"),
        ("karen manning-fuller", "karen manning-fuller"),
    ])
    def test_periods_stripped(self, raw, expected):
        assert normalise_name(raw) == expected


    @pytest.mark.parametrize("raw,expected", [
        ("  anita beaver  ", "anita beaver"),
        (" drew  peacock", "drew peacock"),
        ("ophelia\tplum", "ophelia plum"),
        ("ophelia\t plum", "ophelia plum"),
        ("ophelia \tplum", "ophelia plum"),
        ("clemens\nkurz", "clemens kurz"),
        ("clemens \nkurz", "clemens kurz"),
        ("clemens\n kurz", "clemens kurz"),
    ])
    def test_fix_whitespace(self, raw, expected):
        assert normalise_name(raw) == expected

    def test_idemptotence(self):
        once =normalise_name("Ophelia b,  Hinde")
        assert normalise_name(once) == once


class TestNormaliseEmail:

    def test_lowercases(self):
        assert normalise_email("AVH@Informatik.Uni-Kiel.DE") == "avh@informatik.uni-kiel.de"

    def test_strips_surrounding_whitespace(self):
        assert normalise_email("  avh@x.de  ") == "avh@x.de"

    @pytest.mark.parametrize("blank", ["", None," "])
    def test_empty_input_returns_empty_string(self, blank):
        assert normalise_email(blank) == ""

    def test_is_idempotent(self):
        once = normalise_email("  AVH@X.DE ")
        assert normalise_email(once) == once

    def test_leaves_diacritics(self):
        '''we don't want to strip these as messing with ascii here
        could merge emails that are genuinely different'''
        assert normalise_email('doüghǎl@mágic.ròundabout.ac.uk')=='doüghǎl@mágic.ròundabout.ac.uk'

class TestMintIDFromName:

    @pytest.mark.parametrize("raw,expected", [
        ("nina marwede", "ninamarwede"),
        ("nina   marwede", "ninamarwede"),
        ("  nina   marwede  ", "ninamarwede"),])
    def test_strip_spaces(self, raw, expected):
        assert mint_id_from_name(raw) == expected


    @pytest.mark.parametrize("raw,expected", [
        ("Nina Marwede", "ninamarwede"),
        ("Helen Smith", "helensmith"),
        ("MicHaElDaviEs", "michaeldavies"), ])
    def test_id_is_lowercase(self, raw, expected):
        assert mint_id_from_name(raw) == expected

    @pytest.mark.parametrize("raw,expected", [
        ("nina.marwede", "ninamarwede"),
        ("helen:smith", "helensmith"),
        ("michael/davies", "michaeldavies"),
        ("michael-davies23", "michaeldavies23"),
        ("michael~davies.23", "michaeldavies23"),
        ("michaeldavies23", "michaeldavies23"),
    ])
    def test_id_is_alphanum(self, raw, expected):
        assert mint_id_from_name(raw) == expected

    @pytest.mark.parametrize("raw,expected", [
       ("&£- /%", "")
        ])
    def test_returns_empty_string(self, raw, expected):
        assert mint_id_from_name(raw) == expected

