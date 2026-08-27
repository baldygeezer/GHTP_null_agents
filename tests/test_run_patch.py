import math
import random
from os import PathLike
from pathlib import Path
from typing import Callable

import pytest
from pytest_mock import mocker

from ghtp_null_agents.run_patch import walk_folder, get_path_to_patch, get_graph_name, get_rdf_paths_and_graphs, \
    import_patch

top_folder = "somefolder"
repo_folder_prefix = "some_repofolder_"

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
    folder_path = _create_top_folder(path, top_folder)
    created_folders=[]
    created_files=[]
    for i in range(10):
        repo_folder_name = f"{repo_folder_prefix}{i}"
        subfolder_path = folder_path / repo_folder_name
        content_filename = f"{repo_folder_name}.ttl"
        created_folder , created_file = _folder_helper(subfolder_path, content, i, content_filename)
        created_folders.append(created_folder)
        created_files.append(created_file)
    return created_folders, created_files


class TestRunPatch:
# walk a folder for a list of subfolders
    def test_walk_folder(self, tmp_path):
        expected_folders, _ = _folders_helper(tmp_path, _rdf_content_helper)
        folders = walk_folder(tmp_path / top_folder)
        assert len(folders) == len(expected_folders)
        assert set(folders) == set(expected_folders)

    def test_walk_folder_looks_1_level(self, tmp_path):
        folder1 = _create_top_folder(test_path=tmp_path, folder_name=top_folder)
        folder2 = folder1 / "folder2"
        folder2.mkdir()
        folder2_1 = folder2 / "folder2_1"
        folder2_1.mkdir()
        folder2_2 = folder2 / "folder2_2"
        folder2_2.mkdir()
        folder3 = folder1 / "folder3"
        folder3.mkdir()
        folder3_1 = folder3 / "folder3_1"
        folder3_1.mkdir()
        folder3_2 = folder3 / "folder3_2"
        folder3_2.mkdir()
        folder4 = folder1 / "folder4"
        folder4.mkdir()

        expected_folders = [folder2, folder3, folder4]
        folders = walk_folder(tmp_path / top_folder)
        assert len(folders) ==3
        assert set(folders) == set(expected_folders)

    def test_walk_folder_returns_only_dirs(self, tmp_path):
        folder1 = _create_top_folder(test_path=tmp_path, folder_name=top_folder)
        folder2 = folder1 / "folder2"
        folder2.mkdir()
        text_file = folder1 / "war_and_peace.txt"
        text_file.write_text("hello world")
        folder3 = folder1 / "folder3"
        folder3.mkdir()
        more_text = folder1 / "why_I do_so_love_comic_sans.doc"
        more_text.write_text("hello world")
        expected_folders = [folder2, folder3 ]
        folders = walk_folder(tmp_path / top_folder)
        assert len(folders) ==2
        assert set(folders) == set(expected_folders)
        for folder in folders:
            assert folder.is_dir()

#get a list of tuples (path to patch, folder_name)
    def test_get_path_to_patch(self, tmp_path):
        folder =_create_top_folder(test_path=tmp_path,folder_name=top_folder)
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
        _folders_helper(path=tmp_path, content=_rdf_content_helper)
        r_val=get_rdf_paths_and_graphs(path=tmp_path / top_folder)
        assert isinstance(r_val, list)

    def test_get_rdf_paths_and_graphs_returns_non_empty_list(self, tmp_path):
        _folders_helper(path=tmp_path, content=_rdf_content_helper)
        r_val=get_rdf_paths_and_graphs(path=tmp_path / top_folder)
        assert len(r_val) == 10

    def test_get_rdf_paths_and_graphs_returns_list_of_tuple(self, tmp_path):
        _folders_helper(path=tmp_path, content=_rdf_content_helper)
        r_val=get_rdf_paths_and_graphs(path=tmp_path / top_folder)
        for item in r_val:
            assert isinstance(item, tuple)

    def test_get_rdf_paths_and_graphs_tuples_have_len_2(self, tmp_path):
        _folders_helper(path=tmp_path, content=_rdf_content_helper)
        r_val=get_rdf_paths_and_graphs(path=tmp_path / top_folder)
        for tup in r_val:
            assert len(tup) == 2

    def test_get_rdf_paths_and_graphs_tuples_contain_str(self, tmp_path):
        _folders_helper(path=tmp_path, content=_rdf_content_helper)
        r_val=get_rdf_paths_and_graphs(path=tmp_path / top_folder)
        for tup in r_val:
            assert isinstance(tup[1], str)

    def test_get_rdf_paths_and_graphs_calls_get_path_to_patch(self, tmp_path,mocker ):
        _folders_helper(path=tmp_path, content=_rdf_content_helper)
        mock_get_path_to_patch=mocker.patch("ghtp_null_agents.run_patch.get_path_to_patch")
        r_val=get_rdf_paths_and_graphs(path=tmp_path / top_folder)
        mock_get_path_to_patch.assert_called()
        assert mock_get_path_to_patch.call_count == 10

    def test_get_rdf_paths_and_graphs_calls_get_graph_name(self, tmp_path,mocker ):
        _folders_helper(path=tmp_path, content=_rdf_content_helper)
        mock_get_graph_name=mocker.patch("ghtp_null_agents.run_patch.get_graph_name")
        r_val=get_rdf_paths_and_graphs(path=tmp_path / top_folder)
        mock_get_graph_name.assert_called()
        assert mock_get_graph_name.call_count == 10

    def test_get_rdf_paths_and_graphs_calls_walk_folders(self, tmp_path,mocker ):
        _folders_helper(path=tmp_path, content=_rdf_content_helper)
        mock_walk_folder=mocker.patch("ghtp_null_agents.run_patch.walk_folder")
        r_val=get_rdf_paths_and_graphs(path=tmp_path / top_folder)
        mock_walk_folder.assert_called_once()

    def test_import_patch_calls_requests_put(self, tmp_path, mocker):
        patch_folder = Path(tmp_path / "patch_folder")
        patch_graph = "patch_folder"
        request_mock = mocker.patch("requests.put")
        import_patch(patch_folder, patch_graph)
        request_mock.assert_called_once()


    @pytest.mark.parametrize("i",range(5))
    def test_import_patch_calls_requests_put_with_args(self, i, mocker):
        headers = {"Content-Type": "text/turtle"}
        data = f"{str(i)}wibble".encode()
        patch_folder = Path() / f"patch_folder{i}"
        patch_graph = f"patch_folder{i}"
        request_mock = mocker.patch("requests.put")
        ttl_mock = mocker.patch("ghtp_null_agents.run_patch.read_turtle",return_value=data)
        import_patch(patch_folder, patch_graph)
        request_mock.assert_called_with(headers=headers,
                                            params={"context": f"<http://soton.ac.uk/pars/graphs/{patch_graph}>"},
                                            data=data,
                                            timeout=120,
                                            )

        ttl_mock.assert_called_once_with(patch_folder / f"{patch_graph}.ttl")

# check that a named graph exists in the triplestore

# log a warning if a named graph does not exist

# skip if a named graph does not exist

# check for valid rdf

# log invalid rdf

# skip invalid rdf

# insert rdf into named graph

# log success









