#!/usr/bin/env python

# ***************************************************************************
# *   Copyright (c) 2021 Yorik van Havre <yorik@uncreated.net>              *
# *                                                                         *
# *   This program is free software; you can redistribute it and/or modify  *
# *   it under the terms of the GNU Lesser General Public License (LGPL)    *
# *   as published by the Free Software Foundation; either version 2 of     *
# *   the License, or (at your option) any later version.                   *
# *   for detail see the LICENCE text file.                                 *
# *                                                                         *
# *   This program is distributed in the hope that it will be useful,       *
# *   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
# *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
# *   GNU Library General Public License for more details.                  *
# *                                                                         *
# *   You should have received a copy of the GNU Library General Public     *
# *   License along with this program; if not, write to the Free Software   *
# *   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  *
# *   USA                                                                   *
# *                                                                         *
# ***************************************************************************

"""
ghbackup.py - This script backs up issues, issue comments and pull requests from
a github repo to 3 json files.

If used anonymously, the github API only allows 60 requests per hour, which is
not enough to perform a complete backup (at the time I write this, a full backup
uses around 500 requests, 200 for the issues and 300 for the contents). To make
use of the authentication system, create yourself an access token on github
(under profile icon -> Settings -> Developer settings) and copy the token to 
a file named ".ghbackup" in your home directory or together with this script.

command-line usage:

    ./ghbackup.py [ORG/REPO] : backs up issues and pull requests from the given repository.
                               (note: pull requests are stored together with issues. github
                               considers every pull request an issue, but not every issue
                               a pull request).
                               If no org/repo is given, the default (FreeCAD/FreeCAD)
                               is backed up. 2 json files are created/updated in the
                               current directory. If that directory is git-managed,
                               files will also be committed and pushed.

python usage:

    import ghbackup
    
    repo = "FreeCAD/FreeCAD"
    issues_dict = ghbackup.get_issues(repo)
    comments_dict = ghbackup.get_issue_comments(repo)
    
    with open("issues.json","w") as f:
        json.dump(issues_dict,f,indent=4)
    with open("comments.json","w") as f:
        json.dump(comments_dict,f,indent=4)   
        
    ghbackup.push()
"""


import os
import sys
import requests
import json
import git
import datetime


DEFAULT_REPO = "FreeCAD/FreeCAD"
BASEURL = "https://api.github.com/repos/"
SESSION = requests.Session()
HEADERS = {}
token_file = os.path.join( os.path.abspath(os.path.expanduser("~")), ".ghbackup")
if os.path.exists(token_file):
    with(open(token_file) as f):
        HEADERS = {'Authorization': 'token ' + f.read().strip()}
else:
    token_file = os.path.join( os.path.dirname(__file__), ".ghbackup")
    if os.path.exists(token_file):
        with(open(token_file) as f):
            HEADERS = {'Authorization': 'token ' + f.read().strip()}


def get_data(api_point,page=1):

    """get_data(api_point,[page]): returns a dict from a github API point"""

    print("fetching",api_point,"page",page)
    params = { "state": "all", "page": str(page) }
    result = SESSION.get(url = BASEURL + api_point, params = params, headers = HEADERS)
    data = result.json()
    if data:
        if isinstance(data,dict):
            print("Fetching data fro github failed. Here is the reply from github:")
            print(data)
            sys.exit()
        data.extend( get_data(api_point, page + 1) )
    return data


def get_issues(repo):

    """get_issues(repo): returns a dict from github issues"""

    return get_data(repo+"/issues")


def get_issue_comments(repo):

    """get_issue_comments(repo): returns a dict from github issue comments"""

    return get_data(repo+"/issues/comments")


def get_pulls(repo):

    """get_issue_comments(repo): returns a dict from github issue comments"""

    return get_data(repo+"/pulls")


def backup(repo):

    """backup(repo): backs up issues, issue comments and pull requests into 3 json files"""

    print("Backing up issues...")
    with open("issues.json","w") as f:
        json.dump(get_issues(repo),f,indent=4)
    print("Backing up issue comments...")
    with open("comments.json","w") as f:
        json.dump(get_issue_comments(repo),f,indent=4)
    # pull requests are issues too so already saved
    # print("Backing up pul requests...")
    # with open("pulls.json","w") as f:
    #    json.dump(get_pulls(repo),f,indent=4)
    return True


def push():

    """push(): pushes backups to git repo"""

    try:
        repo = git.Repo(os.path.curdir)
        repo.git.add(update=True)
        repo.index.commit("backup " + str(datetime.date.today()) )
        origin = repo.remote(name='origin')
        origin.push()
        return True
    except:
        return False


if __name__ == "__main__":

    args = sys.argv[1:]
    if len(args) == 1:
        repo = args[0]
    else:
        repo = DEFAULT_REPO
    backup(repo)
    push()
