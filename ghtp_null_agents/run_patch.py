from os import PathLike
from pathlib import Path


def walk_folder(path:Path):
    folders = []
    for sub in Path(path).iterdir():
        folders.extend(sub.iterdir())
    return folders

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
    for folder in Path(path).iterdir():
        patch_path = get_path_to_patch(folder)
        graph_name = get_graph_name(folder)
        result.append((patch_path, graph_name))
    return result

