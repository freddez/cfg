#!/usr/bin/env python3
import argparse
import importlib
import sys
import socket
import os, os.path as osp
import re
import colorama
from git import Repo
from .utils import (
    info,
    error,
    config_error,
    git_hashes,
    colordiff,
    copy_preserve,
    mkdir_copy,
)


FILE_IDENTICAL = 0
FILE_MISSING = 1
FILE_SIZE_DIFFERS = 2
FILE_HASHES_TO_COMPARE = 3
FILE_HASH_DIFFERS = 4
FILE_ATTR_DIFFERS = 5
FILE_TO_HASH = 6

SRC_PATH = "src/"
L_SRC_PATH = len(SRC_PATH)

sys.path.append(".")
try:
    params = importlib.import_module("cfg_params")
except ImportError:
    error("cfg_params.py file missing")
params_mtime = osp.getmtime(params.__file__)
params_map = {
    "=cfg[%s]" % key: getattr(params, key) for key in dir(params) if key == key.upper()
}
for key, value in params_map.items():
    if not isinstance(value, str):
        config_error("%s value should be a string" % key)
cfg_rgxp = re.compile("|".join(map(re.escape, params_map.keys())))


class CfgElement(object):
    def __init__(self, elt, dst_path=None):
        self.type = elt.type
        self.size = elt.size
        self.hexsha = elt.hexsha
        self.path = elt.path[L_SRC_PATH:]
        self.abspath = elt.abspath
        if self.type != "tree":
            basename = osp.basename(self.path)
            if basename.startswith("cfg."):
                self.process_cfg_file(basename)
        self.dst_path = dst_path or osp.join(params.target, self.path)

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
        """
        cfg_file is a template containing =CFG[VAR] patterns, where VAR is a parameter 
        defined in cfg_params.py (see prepare_install_tree_stage_1)
        """
        n = len(basename)
        new_basename = basename[4:]  # suppress ".cfg" prefix
        new_path = self.path[:-n] + new_basename
        new_abspath = self.abspath[:-n] + new_basename
        new_abspath_exists = osp.exists(new_abspath)
        if new_abspath_exists:
            stat = os.stat(new_abspath)
            self.size = stat.st_size
        if (
            not new_abspath_exists
            or params_mtime > stat.st_mtime
            or osp.getmtime(self.abspath) > stat.st_mtime
        ):
            content = open(self.abspath).read()
            content = cfg_rgxp.sub(lambda match: params_map[match.group(0)], content)
            file = open(new_abspath, "w")
            file.write(content)
        self.path = new_path
        self.abspath = new_abspath
        self.hexsha = None
        self.set_difference(FILE_TO_HASH)


class CfgRepo(Repo):
    def __init__(self, *args, **kwargs):
        super(CfgRepo, self).__init__(*args, **kwargs)
        params.target = osp.abspath(params.TARGET)
        if hasattr(params, "HOSTNAME"):
            self.hostname = params.HOSTNAME
        else:
            self.hostname = socket.gethostname()

    def prepare_install_tree_stage_1(self, tree):
        for e in tree:
            if not e.path.startswith(SRC_PATH[:-1]): # temp fix
                continue
            basename = osp.basename(e.path)
            if basename.startswith("cfg-"):
                cfg_host_prefix = "cfg-%s." % self.hostname
                if basename.startswith(cfg_host_prefix):
                    dst_path = osp.join(
                        params.target,
                        e.path[L_SRC_PATH : -len(basename)]
                        + basename[len(cfg_host_prefix) :],
                    )
                    self.elts.append(CfgElement(e, dst_path))
            else:
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
            print("%s :" % e.dst_path)
            if e.difference != FILE_MISSING:
                colordiff(e.dst_path, e.abspath)
            else:
                info("new file")
            if test:
                continue
            if e.type == "tree":
                os.makedirs(e.dst_path)
            else:
                copy_preserve(e.abspath, e.dst_path, new=e.difference == FILE_MISSING)

    def add_command(self, path):
        path = osp.abspath(path)
        if not path.startswith(params.target):
            error("path outside %s dir" % params.target)
        if not osp.exists(path):
            error("path does not exists")
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


def main():
    parser = argparse.ArgumentParser()

    subparsers = parser.add_subparsers(help="commands", dest="command")

    # Install command
    subparsers.add_parser("install", help="Install src content")
    subparsers.add_parser(
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


if __name__ == "__main__":
    main()
