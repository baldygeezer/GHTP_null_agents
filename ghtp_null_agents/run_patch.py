from os import PathLike
from pathlib import Path


def walk_folder(path:Path):
    folders = []
    for sub in Path(path).iterdir():
        folders.extend(sub.iterdir())
    return folders

def get_rdf_paths_and_graphs(path: Path):
  pass

