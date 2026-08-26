from os import PathLike
from pathlib import Path
from typing import Callable

import pytest
from ghtp_null_agents.run_patch import walk_folder, get_path_to_patch, get_graph_name, get_rdf_paths_and_graphs


def _rdf_content_helper(path: Path, i:int|None = None , name:str|None=None):
    rdf_string="""@prefix prov: <http://www.w3.org/ns/prov#> .
            @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

            <https://github.com/test_repo/test/commit/00060e> 
            prov:qualifiedAssociation [ prov:agent <https://github.com/alice> ;
                prov:hadRole <http://purl.org/github2prov/committer> ],
                [ prov:agent <https://github.com/alice> ;
                prov:hadRole <http://purl.org/github2prov/author> ] ;
                prov:wasAssociatedWith <https://github.com/alice> .
                  <https://github.com/alice> a prov:Agent .
                  """
    file_name = name if name else "test_repo.ttl"
    rdf_path = path / file_name
    rdf_path.write_text(rdf_string, encoding="utf-8")
    # assert str(rdf_path).endswith(".ttl")
    assert rdf_path.is_file()
    contents = rdf_path.read_text(encoding="utf-8")
    assert contents.strip() == rdf_string.strip()
    return rdf_path


def _folder_helper(path:Path,
                   content:Callable | None = None,
                   i:int |None = None,
                   content_filename:str|None=None) -> tuple:
    path.mkdir()
    folder_path = path
    content_path = None
    if content:
        content_path = content(path, i) if not content_filename else content(path, i, content_filename)
    return folder_path, content_path

def _create_top_folder(test_path:Path, folder_name:str)->Path:
    folder_path = test_path / folder_name
    folder_path.mkdir()
    return folder_path


def _folders_helper(path:Path, content:Callable |None = None) -> tuple[list[Path], list[Path]] :
    repo_folder_prefix = "some_repofolder_"
    folder_path = _create_top_folder(path, "somefolder")
    created_folders=[]
    created_files=[]
    for i in range(10):
        repo_folder_name = f"{repo_folder_prefix}{i}"
        subfolder_path = folder_path / repo_folder_name
        created_folder , created_file = _folder_helper(subfolder_path, content, i)
        created_folders.append(created_folder)
        created_files.append(created_file)
    return created_folders, created_files


class TestRunPatch:
# walk a folder for a list of subfolders
    def test_walk_folder(self, tmp_path):
        expected_folders, _ = _folders_helper(tmp_path, _rdf_content_helper)
        folders = walk_folder(tmp_path)
        assert len(folders) == len(expected_folders)
        assert set(folders) == set(expected_folders)

#get a list of tuples (path to patch, folder_name)
    def test_get_path_to_patch(self, tmp_path):
        folder =_create_top_folder(test_path=tmp_path,folder_name="somefolder")
        subfolder0, content_path =_folder_helper(path = folder / "sub_folder",
                                                 content = _rdf_content_helper,
                                                 content_filename = "sub_folder.ttl")
        subfolder1, content_path = _folder_helper(path=folder / "wibble_wibble",
                                                  content=_rdf_content_helper,
                                                  content_filename = "wibble_wibble.ttl")

        test_paths = [subfolder1, subfolder0]
        for subfolder in test_paths:
            patch_path=get_path_to_patch(subfolder)
            assert patch_path.is_file()
            assert patch_path.exists()
            assert str(patch_path).endswith(f"{subfolder.name}.ttl")



    def test_get_path_to_patch_raises_error_if_missing_patch(self, tmp_path):
        folder = _create_top_folder(test_path=tmp_path, folder_name="somefolder")
        subfolder0, _ = _folder_helper(path=folder / "sub_folder",
                                       content=_rdf_content_helper,
                                       content_filename="ploppy.ttl")
        subfolder1, _ = _folder_helper(path=folder / "wibble_wibble",
                                       content=_rdf_content_helper,
                                       content_filename="wibble_wibble.trig")
        subfolder2, _ = _folder_helper(path=folder / "ding_dong",
                                       content=_rdf_content_helper,
                                       content_filename="dong_ding.ttl")
        subfolder3 = folder / "nothingtoseehere"
        subfolder3.mkdir()
        test_paths = [subfolder1, subfolder0, subfolder2, subfolder3]
        for subfolder in test_paths:
            with pytest.raises(FileNotFoundError):
                 get_path_to_patch(subfolder)

    def test_get_graph_returns_graph_name(self, tmp_path):
        folder = _create_top_folder(test_path=tmp_path, folder_name="somefolder")
        subfolder0, content_path0 = _folder_helper(path=folder / "sub_folder",
                                                  content=_rdf_content_helper,
                                                  content_filename="sub_folder.ttl")
        subfolder1, content_path1 = _folder_helper(path=folder / "wibble_wibble",
                                                  content=_rdf_content_helper,
                                                  content_filename="wibble_wibble.ttl")

        test_graphs = [(subfolder1.name,subfolder1), (subfolder0.name,subfolder0)]
        for graph in test_graphs:
            graph_name = get_graph_name(graph[1])
            assert graph_name == graph[0]

    def test_get_graph_raises_error_if_no_result(self, tmp_path):
        folder = _create_top_folder(test_path=tmp_path, folder_name="somefolder")
        subfolder0, content_path0 = _folder_helper(path=folder / "sub_folder",
                                                   content=_rdf_content_helper,
                                                   content_filename="not_a_duck.ttl")
        subfolder1, content_path1 = _folder_helper(path=folder / "wibble_wibble",
                                                   content=_rdf_content_helper,
                                                   content_filename="quacks_like_a_penguin.ttl")

        test_graphs = [(subfolder1.name, subfolder1), (subfolder0.name, subfolder0)]
        for graph in test_graphs:
            with pytest.raises(ValueError):
                graph_name = get_graph_name(graph[1])



    def test_get_rdf_paths_and_graphs_returns_list(self, tmp_path):
        r_val=get_rdf_paths_and_graphs(path=tmp_path)
        assert isinstance(r_val, list)

    def test_get_rdf_paths_and_graphs_returns_list_of_tuple(self, tmp_path):
        r_val=get_rdf_paths_and_graphs(path=tmp_path)
        for item in r_val:
            assert isinstance(item, tuple)

# check that a named graph exists in the triplestore

# log a warning if a named graph does not exist

# skip if a named graph does not exist

# check for valid rdf

# log invalid rdf

# skip invalid rdf

# insert rdf into named graph

# log success









