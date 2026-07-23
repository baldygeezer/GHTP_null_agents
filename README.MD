resolve orphan commits in github2prov data.
These arise where history is imported from another VCS, or git platform, or where commits are made via the UI
in those circumstances there is no github user id, and so no attibution/assocation is recorded. However a given name and email address often is present. Tis also occurs on other commits where there is a username


This package uses the crawled commit data (commits.json), to resolve github userids where possible. It can then generate  the missing prov triples for associations and roles