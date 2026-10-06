import subprocess
import time
from pathlib import Path

import pytest
import requests
from fixtures import rdf_valid_prov
from run_patch import import_patch

COMPOSE_FILE = Path(__file__).resolve().parent.parent / "graph-db" / "docker-compose.yml"
BASE_URL = "http://localhost:7205"
REPO = "test"


def _wait_until_ready(base_url, repo, timeout=120):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if requests.get(f"{base_url}/repositories/{repo}/size", timeout=2).ok:
                return
        except requests.ConnectionError:
            pass
        time.sleep(1)
    raise TimeoutError(f"GraphDB repo '{repo}' wasn't ready in time")


@pytest.fixture(scope="session")
def graphdb():
    subprocess.run(["docker", "compose", "-f", str(COMPOSE_FILE), "up", "-d"], check=True)
    _wait_until_ready(BASE_URL, REPO)
    yield BASE_URL
    subprocess.run(["docker", "compose", "-f", str(COMPOSE_FILE), "down"], check=True)


@pytest.fixture
def clean_graph(graphdb):
    graph_uri = "http://soton.ac.uk/pars/graphs/patch_folder0"
    requests.delete(
        f"{graphdb}/repositories/{REPO}/statements",
        params={"context": f"<{graph_uri}>"},
    )
    yield


@pytest.mark.integration
def test_import_patch_inserts_triples_into_named_graph(graphdb, clean_graph, tmp_path,rdf_valid_prov):
    ttl_path = tmp_path / "patch_folder0.ttl"
    ttl, i = rdf_valid_prov
    ttl_path.write_text(ttl)
    graph=f"patch_folder{i}"
    graph_uri = f"http://soton.ac.uk/pars/graphs/{graph}"

    import_patch(ttl_path.parent, graph, BASE_URL, REPO)

    in_named_graph = requests.get(
        f"{graphdb}/repositories/{REPO}",
        params={"query": f"ASK {{ GRAPH <{graph_uri}> {{ ?s ?p ?o }} }}"},
        headers={"Accept": "application/sparql-results+json"},
    ).json()["boolean"]

    in_default_graph = requests.get(
        f"{graphdb}/repositories/{REPO}",
        params={"query": "ASK { ?s ?p ?o }"},
        headers={"Accept": "application/sparql-results+json"},
    ).json()["boolean"]

    assert in_named_graph is True
