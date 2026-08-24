resolve orphan commits in github2prov data.
These arise where history is imported from another VCS, or git platform, or where commits are made via the UI
in those circumstances there is no github user id, and so no attibution/assocation is recorded. However a given name and 
email address often is present. This also occurs on other commits where there is a username

This package uses the crawled commit data (commits.json) from a github2prov result to resolve github userids where 
possible. It can then generate the missing prov triples for associations and roles.

Usage
From the cloned repo folder:
run ```poetry install```
if you have a folder full of github2prov results:
run ```python ghtp_null_agents/resolve_orphan_commits.py --folder <path to folder>```
if you have a commits.json:
run ```python ghtp_null_agents/resolve_orphan_commits.py --commits <path to json file>```
if you have a custom lookup file you can use the ```--lookup argument```

if you want to build a lookup json file run 
```python ghtp_null_agents/lookup_builder.py --commits <path to json file> ```
use the ```--lookup``` arg to specify a location to save the lookup
use the ```--conflicts``` arg to specify a location for the conflicts log


