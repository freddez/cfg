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

    def prepare_install_tree_stage_1(self, tree):
        for e in tree:
            if e.path.startswith(SRC_PATH):
                path = e.path[L_SRC_PATH:]
                dst_path = os.path.join(params.TARGET, path)
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
                self.prepare_install_treestage_1(e)

    def prepare_install_tree(self, tree):
        self.prepare_install_tree_stage_1(self, tree)
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

    def install(self, test=False):
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

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("command", help="cfg command")
    args = parser.parse_args()
    repo = CfgRepo()
    if args.command in ("install", "test"):
        repo.install(test=args.command == "test")
