#!/usr/bin/env python
# Helper script to create and publish a new asyncdgt release.

import os
import sys
import configparser
import requests
import bs4
import asyncdgt


def system(command):
    print(command)
    if 0 != os.system(command):
        sys.exit(1)


def check_git():
    print("--- CHECK GIT ----------------------------------------------------")
    system("git diff --exit-code")


def test():
    print("--- TEST ---------------------------------------------------------")
    system("python test.py")


def check_readme():
    print("--- CHECK README -------------------------------------------------")
    system("python setup.py --long-description | rst2html --strict --no-raw > /dev/null")


def tag_and_push():
    print("--- TAG AND PUSH -------------------------------------------------")
    tagname = "v{0}".format(asyncdgt.__version__)
    release_filename = "release-{0}.txt".format(tagname)

    if not os.path.exists(release_filename):
        print(">>> Creating {0} ...".format(release_filename))
        headline = "asyncdgt {0}".format(tagname)
        release_txt.write(headline + os.linesep)

    with open(release_filename, "r") as release_txt:
        release = release_txt.read().strip() + os.linesep
        print(release)

    with open(release_filename, "w") as release_txt:
        release_txt.write(release)

    guessed_tagname = input(">>> Sure? Confirm tagname: ")
    if guessed_tagname != tagname:
        print("Actual tagname is: {0}".format(tagname))
        sys.exit(1)

    system("git tag {0} -s -F {1}".format(tagname, release_filename))
    system("git push origin master {0}".format(tagname))
    return tagname


def pypi():
    print("--- PYPI ---------------------------------------------------------")
    system("python setup.py sdist upload")


def pythonhosted(tagname):
    print("--- PYTHONHOSTED -------------------------------------------------")

    print("Creating pythonhosted.zip ...")
    system("cd docs; make singlehtml; cd ..")
    system("cd docs/_build/singlehtml; zip -r ../../../pythonhosted.zip *; cd ../../..")

    print("Getting credentials ...")
    config = configparser.ConfigParser()
    config.read(os.path.expanduser("~/.pypirc"))
    username = config.get("pypi", "username")
    password = config.get("pypi", "password")
    auth = requests.auth.HTTPBasicAuth(username, password)
    print("Username: {0}".format(username))

    print("Getting CSRF token ...")
    session = requests.Session()
    res = session.get("https://pypi.python.org/pypi?:action=pkg_edit&name=asyncdgt", auth=auth)
    if res.status_code != 200:
        print(res.text)
        print(res)
        sys.exit(1)
    soup = bs4.BeautifulSoup(res.text, "html.parser")
    csrf = soup.find("input", {"name": "CSRFToken"})["value"]
    print("CSRF: {0}".format(csrf))

    print("Uploading ...")
    with open("pythonhosted.zip", "rb") as zip_file:
        res = session.post("https://pypi.python.org/pypi", auth=auth, data={
            "CSRFToken": csrf,
            ":action": "doc_upload",
            "name": "asyncdgt",
        }, files={
            "content": zip_file,
        })
    if res.status_code != 200 or not tagname in res.text:
        print(res)
        sys.exit(1)

    print("Done.")


def github_release(tagname):
    print("--- GITHUB RELEASE -----------------------------------------------")
    print("https://github.com/niklasf/python-asyncdgt/releases/tag/{0}".format(tagname))


if __name__ == "__main__":
    check_git()
    check_readme()
    test()
    tagname = tag_and_push()
    pypi()
    tagname = "v0.0.1"
    pythonhosted(tagname)
    github_release(tagname)
