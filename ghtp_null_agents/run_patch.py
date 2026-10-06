
from pathlib import Path

import requests
from rdflib import Graph

def walk_folder(path:Path):
    return [entry for entry in Path(path).iterdir() if entry.is_dir()]

def get_path_to_patch(folder:Path):
    folder = Path(folder)
    patch_path = folder / f"{folder.name}.ttl"
    if not patch_path.is_file():
        raise FileNotFoundError(patch_path)
    return patch_path

def get_graph_name(folder_path:Path)->str:
    folder_path = Path(folder_path)
    patch_path = folder_path / f"{folder_path.name}.ttl"
    if not patch_path.is_file():
        raise ValueError(f"No patch found for {folder_path}")
    return folder_path.name

def get_rdf_paths_and_graphs(path: Path)->list[tuple[Path, str]]:
    result = []
    for folder in walk_folder(path):
        patch_path = get_path_to_patch(folder)
        graph_name = get_graph_name(folder)
        result.append((patch_path, graph_name))
    return result

def read_turtle(path:Path)->bytes:
    path = Path(path)
    try:
        Graph().parse(path)
    except Exception as e:
        raise ValueError(f"Bad Turtle syntax: could not read the file at {path}") from e
    content = path.read_bytes()
    if b"http://www.w3.org/ns/prov#" not in content:
        raise ValueError(f"The turtle file at {path} does not appear to contain prov data")
    return content

def graph_exists_in_db():
    pass

def graph_db_is_up():
    pass

def import_patch(patch_path:Path, graph_name:str, endpoint:str, repo:str="repo", ):
    data = read_turtle(Path(patch_path) / f"{graph_name}.ttl")
    requests.put(
        url=f"{endpoint}/repositories/{repo}/statements",
        headers={"Content-Type": "text/turtle"},
        params={"context": f"<http://soton.ac.uk/pars/graphs/{graph_name}>"},
        data=data,
        timeout=120,
    )

