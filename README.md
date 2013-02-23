# Usage

1. Set the settings in config.yaml.
2. `python trac_to_github.py`

All your Trac tickets will be imported into Github. 

The appropriate milestones are also created. 

Reading data from Trac requires XMLRPC support.

The fields are mapped as follows:
 
    Github      Trac
    ======      ====
    title       summary
    body        description
    assignee    n/a
    milestone   new milestone based on Trac milestone
    labels      n/a
    comment     All unmapped Trac data

## About duplicates

Duplicate milestones are not created even if duplicate tickets are imported.

You can choose to ignore all suspected duplicate tickets or be prompted for each. Set this in config.yaml.

## Caching

A cache file is created with the Trac data; this is for if something goes wrong during the Github import. The next time you run it, it will read from the file instead of from the Trac site. To prevent it from using the cache, just delete the file {projectname}.pickle.

Warning: this `*.pickle` file stores your password in plain text. Don't share it.

# Development notes

Trac data for each issue comes via XMLRPC and is formatted like this:

    [236, <DateTime '20090404T04:15:04' at 1064a4518>, <DateTime '20090405T00:00:54' at 1064a4050>, 
    {'status': 'closed', 'changetime': <DateTime '20090405T00:00:54' at 1064a4128>, 'type': 'defect', 
    'description': 'The installer crashes immediately under WinXP SP2 (Parallels virtual machine).\n
    It works fine under virtual machines for Xp SP3, and on a Thinkpad with XP SP2.  However, the 
    crash should be resolved before release, as it suggests the possibility of crashing on other 
    machine configurations.\n\nInitial testing makes me suspect a problem with GetWindowsVersion 
    (although that function has been used for a while and used to work ok)', 
    'reporter': 'marisa-demeglio', 'cc': '', 'tt_spent': '1d', 'milestone': 'Release Candidate 2', 
    '_ts': '2009-04-05 00:00:54+00:00', 'tt_remaining': '1d', 
    'summary': 'installer crashes under win xp sp2 parallels virtual machine', 
    'priority': 'major', 'owner': 'marisa-demeglio', 'time': <DateTime '20090404T04:15:04' at 1064a42d8>, 
    'keywords': '', 'tt_estimated': '1d', 'resolution': 'fixed'}]

For Github, I am using [PyGithub](http://vincent-jacques.net/PyGithub/reference_of_classes/).



