import stat
import os
import os.path as osp
import sys
import shutil
from termcolor import colored
from subprocess import run, PIPE


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
