from ghtp_null_agents.lookup_builder import extract_login
from tests.fixtures import user_json





class TestExctract_login:

    def test_graphql_user_object(self):
        assert extract_login(user_json("avanhoorn")) == "avanhoorn"