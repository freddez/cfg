#!/usr/bin/env python3
import argparse
from git import Repo
import importlib
import sys
import os
import os.path as osp
import re
import stat
import shutil
from subprocess import run, PIPE
import colorama
from termcolor import colored


def human_stat(path):
    return stat.filemode(os.stat(path).st_mode)


def error(error_type, message=None):
    if message is None:
        message = error_type
        error_type = "ERROR"
    print("%s : %s" % (colored(error_type, "red"), message))
    sys.exit(0)


def config_error(message):
    error("CONFIG ERROR", message)


def git_hashes(str_paths):
    proc = run(
        ["git", "hash-object", "--stdin-paths"],
        stdout=PIPE,
        input=bytes(str_paths, "utf-8"),
    )
    assert proc.returncode == 0
    return proc.stdout.decode().split("\n")[:-1]


def colordiff(file1, file2):
    run(["colordiff", file1, file2])


FILE_IDENTICAL = 0
FILE_MISSING = 1
FILE_SIZE_DIFFERS = 2
FILE_HASHES_TO_COMPARE = 3
FILE_HASH_DIFFERS = 4
FILE_ATTR_DIFFERS = 5
FILE_TO_HASH = 6

MESSAGE = {
    FILE_IDENTICAL: "files identical",
    FILE_MISSING: "file missing",
    FILE_SIZE_DIFFERS: "file size differs",
    FILE_HASHES_TO_COMPARE: "file hashes to compare",
    FILE_ATTR_DIFFERS: "file attributes differs",
}

SRC_PATH = "src/"
L_SRC_PATH = len(SRC_PATH)

sys.path.append(".")
params = importlib.import_module("cfg_params")
params_mtime = osp.getmtime(params.__file__)
replacement_map = {
    "=cfg[%s]" % key: getattr(params, key) for key in dir(params) if key == key.upper()
}
for key, value in replacement_map.items():
    if not isinstance(value, str):
        config_error("%s value should be a string" % key)
cfg_rgxp = re.compile("|".join(map(re.escape, replacement_map.keys())))


def dir_diff(src_path, dst_path):
    "Check differences between two paths. Used to check permissions changes"
    proc = run(["rsync", "-nrpgovi", src_path + "/", dst_path + "/"], stdout=PIPE)
    assert proc.returncode == 0
    dir_diff = {}
    for line in proc.stdout.decode().split("\n")[1:-4]:
        change = line[:11]
        path = line[12:]
        if path[-1] == "/":
            path = path[:-1]
        dir_diff[path] = change
    return dir_diff


def mkdir_copy(src_path, dst_path, sub_path):
    path = ""
    for dir in osp.dirname(sub_path).split("/"):
        path += "/" + dir
        if not osp.exists(dst_path + path):
            os.mkdir(dst_path + path)
            shutil.copystat(src_path + path, dst_path + path)
    shutil.copy2(osp.join(src_path, sub_path), osp.join(dst_path, sub_path))


class CfgElement(object):
    def __init__(self, elt):
        self.type = elt.type
        self.size = elt.size
        self.hexsha = elt.hexsha
        self.path = elt.path[L_SRC_PATH:]
        self.abspath = elt.abspath
        if self.type != "tree":
            basename = osp.basename(self.path)
            if basename.startswith("cfg."):
                self.process_cfg_file(basename)
        self.dst_path = osp.join(params.target, self.path)

    _difference = None

    @property
    def difference(self):
        if self._difference is None:
            if osp.exists(self.dst_path):
                if self.type == "tree":
                    self._difference = FILE_IDENTICAL
                elif self.size != osp.getsize(self.dst_path):
                    self._difference = FILE_SIZE_DIFFERS
                else:
                    self._difference = FILE_HASHES_TO_COMPARE
            else:
                self._difference = FILE_MISSING
        return self._difference

    def set_difference(self, difference=None):
        self._difference = difference

    def process_cfg_file(self, basename):
        n = len(basename)
        new_basename = basename[4:]  # suppress ".cfg" prefix
        new_path = self.path[:-n] + new_basename
        new_abspath = self.abspath[:-n] + new_basename
        if osp.exists(new_abspath) and (
            params_mtime > osp.getmtime(new_abspath)
            or osp.getmtime(self.abspath) > osp.getmtime(new_abspath)
        ):
            content = open(self.abspath).read()
            content = cfg_rgxp.sub(
                lambda match: replacement_map[match.group(0)], content
            )
            file = open(new_abspath, "w")
            file.write(content)
        shutil.copystat(self.abspath, new_abspath)
        self.path = new_path
        self.abspath = new_abspath
        self.hexsha = None
        self.set_difference = FILE_TO_HASH


class CfgRepo(Repo):
    def __init__(self, *args, **kwargs):
        super(CfgRepo, self).__init__(*args, **kwargs)
        params.target = osp.abspath(params.TARGET)

    def prepare_install_tree_stage_1(self, tree):
        for e in tree:
            if e.path.startswith(SRC_PATH):
                self.elts.append(CfgElement(e))
            if e.type == "tree":
                self.prepare_install_tree_stage_1(e)

    def prepare_install_tree(self, tree):
        self.prepare_install_tree_stage_1(tree)
        cfg_elts = [elt for elt in self.elts if elt.difference == FILE_TO_HASH]
        if cfg_elts:
            paths_to_hash = ""
            for elt in cfg_elts:
                paths_to_hash += elt.abspath + "\n"
            hashes = git_hashes(paths_to_hash)
            for i, elt in enumerate(cfg_elts):
                elt.hexsha = hashes[i]
                elt.set_difference()
        dst_paths_to_hash = ""
        for cfg_elt in self.elts:
            if cfg_elt.difference == FILE_HASHES_TO_COMPARE:
                dst_paths_to_hash += cfg_elt.dst_path + "\n"
        if dst_paths_to_hash:
            dst_hashes = git_hashes(dst_paths_to_hash)
            i = 0
            for elt in self.elts:
                if elt.difference == FILE_HASHES_TO_COMPARE:
                    if dst_hashes[i] == elt.hexsha:
                        elt.set_difference(FILE_IDENTICAL)
                    else:
                        elt.set_difference(FILE_HASH_DIFFERS)
                    i += 1

    def install_command(self, test=False):
        if test:
            print("checking content...")
        else:
            print("installing...")
        colorama.init()
        if self.is_dirty():
            error("uncommited files exists")
        self.elts = []
        self.prepare_install_tree(self.active_branch.commit.tree)
        for e in self.elts:
            if e.difference == FILE_IDENTICAL:
                continue
            print("%s : %s" % (e.dst_path, colored(MESSAGE[e.difference], "green")))
            if e.difference != FILE_MISSING:
                colordiff(e.dst_path, e.abspath)
            if test:
                continue
            if e.difference != FILE_MISSING and e.type != "tree":
                shutil.move(e.dst_path, e.dst_path + ".old")
            if e.type == "tree":
                os.makedirs(e.dst_path)
            else:
                shutil.copy2(e.abspath, e.dst_path)
        print("checking attributes changes :")
        dird = dir_diff(SRC_PATH, params.target)
        for e in self.elts:
            if test and e.difference == FILE_MISSING:
                continue
            change = dird.get(e.path)
            if change:
                dst_perms = human_stat(e.dst_path)
                src_perms = human_stat(e.abspath)
                if src_perms != dst_perms:
                    print(
                        "%s %s %s"
                        % (
                            colored(src_perms, "green"),
                            colored(dst_perms, "red"),
                            e.path,
                        )
                    )
                else:
                    print(e.path)
                if not test:
                    shutil.copystat(e.abspath, e.dst_path)

    def add_command(self, path):
        path = osp.abspath(path)
        if not path.startswith(params.target):
            error("path outside %s dir" % params.target)
        if not osp.exists(path):
            print(colored("ERROR", "red"), " : path does not exists")
            return
        if params.target == "/":
            sub_path = path[len(params.target) :]
        else:
            sub_path = path[len(params.target) + 1 :]
        src_path = osp.join(self.working_dir, SRC_PATH, sub_path)
        mkdir_copy(params.target, osp.join(self.working_dir, SRC_PATH), sub_path)
        self.index.add([src_path])  # git add
        basename = osp.basename(src_path)
        self.index.commit("[cfg] : +%s" % basename)  # git commit
        print("%s added to the repository" % basename)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    subparsers = parser.add_subparsers(help="commands", dest="command")

    # Install command
    install_parser = subparsers.add_parser("install", help="Install src content")
    install_parser = subparsers.add_parser(
        "check", help="Perform a trial install to show what's changed"
    )

    #  Add command
    add_parser = subparsers.add_parser(
        "add", help="Import file in repository and commit it"
    )
    add_parser.add_argument("path", action="store", help="Full path of file to add")

    args = parser.parse_args()
    repo = CfgRepo()
    if args.command == "install":
        repo.install_command(test=False)
    if args.command == "check":
        repo.install_command(test=True)
    elif args.command == "add":
        repo.add_command(args.path)
