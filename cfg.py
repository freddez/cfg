#!/usr/bin/env python3
import argparse
from git import Repo
import importlib
import sys
import os
import shutil
from subprocess import run, PIPE
import colorama
from termcolor import colored


FILE_IDENTICAL = 0
FILE_MISSING = 1
FILE_SIZE_DIFFERS = 2
FILE_SIZE_IDENTICAL = 3
FILE_HASH_DIFFERS = 4

MESSAGE = {
    FILE_IDENTICAL: "files identical",
    FILE_MISSING: "file missing",
    FILE_SIZE_DIFFERS: "files sizes differs",
    FILE_SIZE_IDENTICAL: "files sizes identical",
    FILE_HASH_DIFFERS: "files hashes differs",
}

SRC_PATH = "src/"
L_SRC_PATH = len(SRC_PATH)

sys.path.append(".")
params = importlib.import_module("cfg_params")


def git_hashes(str_paths):
    proc = run(
        ["git", "hash-object", "--stdin-paths"],
        stdout=PIPE,
        input=bytes(str_paths, "utf-8"),
    )
    assert proc.returncode == 0
    return proc.stdout.decode().split("\n")[:-1]


class CfgRepo(Repo):
    def __init__(self, *args, **kwargs):
        super(CfgRepo, self).__init__(*args, **kwargs)
        self.target = os.path.abspath(params.TARGET)

    def prepare_install_tree_stage_1(self, tree):
        for e in tree:
            if e.path.startswith(SRC_PATH):
                path = e.path[L_SRC_PATH:]
                dst_path = os.path.join(self.target, path)
                if os.path.exists(dst_path):
                    if e.type == "tree":
                        difference = FILE_IDENTICAL
                    elif e.size != os.path.getsize(dst_path):
                        difference = FILE_SIZE_DIFFERS
                    else:
                        difference = FILE_SIZE_IDENTICAL
                        self.dst_paths_to_hash += dst_path + "\n"
                else:
                    difference = FILE_MISSING
                self.elts.append([e, dst_path, difference])
            if e.type == "tree":
                self.prepare_install_tree_stage_1(e)

    def prepare_install_tree(self, tree):
        self.prepare_install_tree_stage_1(tree)
        if self.dst_paths_to_hash:
            dst_hashes = git_hashes(self.dst_paths_to_hash)
            i = 0
            for elt in self.elts:
                if elt[2] == FILE_SIZE_IDENTICAL:
                    if dst_hashes[i] == elt[0].hexsha:
                        elt[2] = FILE_IDENTICAL
                    else:
                        print(elt[0].path, dst_hashes[i], elt[0].hexsha)
                        elt[2] = FILE_HASH_DIFFERS
                    i += 1

    def install_command(self, test=False):
        colorama.init()
        if self.is_dirty():
            print(colored("ERROR", "red"), " : uncommited files exists")
            return
        self.elts = []
        self.dst_paths_to_hash = ""
        self.prepare_install_tree(self.active_branch.commit.tree)
        for e, dst_path, difference in self.elts:
            if difference == FILE_IDENTICAL:
                continue
            print(colored(MESSAGE[difference], "green"), dst_path)
            if test:
                continue
            if difference != FILE_MISSING:
                shutil.move(dst_path, dst_path + ".old")
            if e.type == "tree":
                os.makedirs(dst_path)
            else:
                shutil.copy2(e.path, dst_path)
        print(colored("TODO : check permissions", "red"))

    def import_command(self, path):
        path = os.path.abspath(path)
        if not path.startswith(self.target):
            print(colored("ERROR", "red"), " : path outside %s dir" % self.target)
            return
        if not os.path.exists(path):
            print(colored("ERROR", "red"), " : path does not exists")
            return
        if self.target == "/":
            sub_path = path[len(self.target) :]
        else:
            sub_path = path[len(self.target) + 1 :]
        src_path = os.path.join(self.working_dir, SRC_PATH, sub_path)
        shutil.copy2(path, src_path)
        self.index.add([src_path])  # git add
        self.index.commit("[cfg] : +%s" % os.path.basename(src_path))  # git commit


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    subparsers = parser.add_subparsers(help="commands", dest="command")

    # Install command
    install_parser = subparsers.add_parser("install", help="Install src content")
    install_parser.add_argument(
        "--test",
        default=False,
        action="store_true",
        help="perform a trial install to show what's changed",
    )

    #  Add command
    add_parser = subparsers.add_parser(
        "import", help="Import file in repository and commit it"
    )
    add_parser.add_argument("path", action="store", help="Full path of file to add")

    args = parser.parse_args()
    repo = CfgRepo()
    if args.command == "install":
        repo.install_command(test=args.test)
    elif args.command == "import":
        repo.import_command(args.path)
