from os import PathLike
from pathlib import Path
from typing import Callable

import pytest
from ghtp_null_agents.run_patch import walk_folder

def _rdf_content_helper(path: Path, i:int):
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
    rdf_path = path / "test_repo_test.json"
    rdf_path.write_text(rdf_string, encoding="utf-8")
    return rdf_path


def _folder_helper(path:Path, content:Callable | None = None, i:int |None = None) -> tuple:
    path.mkdir()
    folder_path = path
    content_path =None
    if content:
        content_path = content(path, i)
    return folder_path, content_path

def _create_top_folder(test_path:Path, folder_name:str):
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
    # def test_get__path_to_patch(self, folder_path):




# check that a named graph exists

# log a warning if a named graph does not exist

# skip if a named graph does not exist

# check for valid rdf

# log invalid rdf

# skip invalid rdf

# insert rdf into named graph

# log success









