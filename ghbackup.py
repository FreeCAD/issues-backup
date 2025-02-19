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

    ./ghbackup.py [Options] [ORG/REPO]

        backs up issues and pull requests from the given repository.
        (note: pull requests are stored together with issues. github
        considers every pull request an issue, but not every issue
        a pull request).
        If no org/repo is given, the default (FreeCAD/FreeCAD)
        is backed up. 2 json files are created/updated in the
        current directory. If that directory is git-managed,
        files will also be committed and pushed.
        Options can be:
        
        --all : fetches all issues (open and closed). Otherwise, only
                open issues are fetched
        --push : git pushes the changes 

python usage:

    import ghbackup

    repo = "FreeCAD/FreeCAD"
    issues = ghbackup.get_issues(repo)
    comments = ghbackup.get_issue_comments(repo)

    # saving json data
    with open("issues.json","w") as f:
        json.dump(issues,f,indent=4)
    with open("comments.json","w") as f:
        json.dump(comments,f,indent=4)

    # saving attachments
    imagelinks = get_image_links(issues) + get_image_links(comments)
    backup_files(imagelinks,"images")
    filelinks = get_file_links(issues) + get_file_links(comments)
    backup_files(filelinks,"files")

    ghbackup.push()
"""


import os
import sys
import requests
import json
import git
import datetime
import re


DEFAULT_REPO = "FreeCAD/FreeCAD"
BASEURL = "https://api.github.com/repos/"
SESSION = requests.Session()
HEADERS = {}
# look for github user token this folder and ~$HOME
token_file = os.path.join( os.path.dirname(__file__), ".ghbackup")
if os.path.exists(token_file):
    with open(token_file) as f:
        HEADERS = {'Authorization': 'token ' + f.read().strip()}
else:
    token_file = os.path.join( os.path.abspath(os.path.expanduser("~")), ".ghbackup")
    if os.path.exists(token_file):
        with open(token_file) as f:
            HEADERS = {'Authorization': 'token ' + f.read().strip()}



def get_data_page(api_point, page=1, allpages=False):

    """get_data_page(api_point,[page,allpages]): returns a dict from a page of an github API point"""

    print("    Fetching",api_point,"page",page)
    if allpages:
        params = { "state": "all", "page": str(page) }
    else:
        params = { "page": str(page) }
    result = SESSION.get(url = BASEURL + api_point, params = params, headers = HEADERS)
    data = result.json()
    return data


def get_data(api_point, page=1, allpages=False):
    
    """get_data(api_point,[page,allpages]): returns a dict from a github API point"""

    result = []
    while True:
        data = get_data_page(api_point, page, allpages)
        if data:
            if isinstance(data,dict):
                print("Fetching data fro github failed. Here is the reply from github:")
                break
            result.extend(data)
            page += 1
        else:
            break
    return result


def get_issues(repo, allpages=False):

    """get_issues(repo): returns a dict from github issues"""

    return get_data(repo+"/issues", allpages=allpages)


def get_issue_comments(repo, allpages=False):

    """get_issue_comments(repo): returns a dict from github issue comments"""

    return get_data(repo+"/issues/comments", allpages=allpages)


def get_image_links(data):

    """get_image_links(data): finds attached image links in the given dict (issues or comments)"""

    links = re.findall(r"https\:\/\/user-images.githubusercontent\.com/.*?\.(?:jpg|jpeg|png|gif|bmp)",json.dumps(data))
    links2 = []
    for l in links:
        if " " in l:
            pass
            #print("Wrong image link:",l)
        else:
            links2.append(l)
    return links2


def get_file_links(data):

    """get_file_links(data): finds attached file links in the given dict (issues or comments)"""

    return re.findall(r"(https\:\/\/github.com/"+repo.replace(r"/",r"\/")+r"\/files\/.*?)\)",json.dumps(data))


def backup_files(links,target):

    """backup_files(links,target): downloads all links from the given link list, and saves them under
    attachments/<target>. Skips existing files."""

    cwd = os.getcwd()
    folder = os.path.join(cwd,"issue-attachments",target)
    if not os.path.isdir(folder):
        os.makedirs(folder)
    for link in links:
        if ">" in link:
            link = link.split(">")[0]
        name = link.split("/")[-1]
        path = os.path.join(folder,name)
        if not os.path.exists(path):
            response = requests.get(link)
            with open(path,"wb") as f:
                print("saving",name)
                f.write(response.content)


def push():

    """push(): pushes backups to git repo"""

    try:
        repo = git.Repo(os.path.curdir)
        repo.git.add(all=True)
        commitmsg = "Issues backup " + str(datetime.date.today())
        repo.index.commit(commitmsg)
        origin = repo.remote(name='origin')
        origin.push()
        print("Pushed revision",commitmsg)
        return True
    except:
        return False


def backup(repo, attachments=True, allpages=False):

    """backup(repo): backs up issues, issue comments and pull requests into 3 json files"""

    print("Backing up issues...")
    with open("issues.json","w") as f:
        issues = get_issues(repo, allpages)
        json.dump(issues,f,indent=4)
    print("Backing up issue comments...")
    with open("comments.json","w") as f:
        comments = get_issue_comments(repo, allpages)
        json.dump(comments,f,indent=4)
    if attachments:
        print("Backing up image attachments...")
        imagelinks = get_image_links(issues)
        imagelinks.extend(get_image_links(comments))
        backup_files(imagelinks,"images")
        print("Backing up file attachments...")
        filelinks = get_file_links(issues)
        filelinks.extend(get_file_links(comments))
        backup_files(filelinks,"files")
    return True


if __name__ == "__main__":

    args = sys.argv[1:]
    allpages = False
    dopush = False
    attachments = True
    repo = DEFAULT_REPO
    if len(args) >= 1:
        repo = args[-1]
        if "--all" in args:
            allpages = True
        if "--push" in args:
            dopush = True
        if "--noattachments" in args:
            attachments = False
    backup(repo, attachments=attachments, allpages=allpages)
    if dopush:
        push()
