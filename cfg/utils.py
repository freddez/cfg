import os
import os.path as osp
import sys
import shutil
from termcolor import colored
from subprocess import run, PIPE


def error(error_type, message=None):
    if message is None:
        message = error_type
        error_type = "ERROR"
    print("%s : %s" % (colored(error_type, "red"), message))
    sys.exit(0)


def config_error(message):
    error("CONFIG ERROR", message)


def info(message):
    print("%s" % (colored(message, "green")))


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


def copy_preserve(src_path, dst_path, new):
    if not new:
        dst_path_old = dst_path + ".old"
        shutil.move(dst_path, dst_path_old)
    shutil.copy2(src_path, dst_path)
    if not new:
        os.chmod(dst_path, os.stat(dst_path_old).st_mode)


def mkdir_copy(src_path, dst_path, sub_path):
    path = ""
    for dir in osp.dirname(sub_path).split("/"):
        path += "/" + dir
        if not osp.exists(dst_path + path):
            os.mkdir(dst_path + path)
            shutil.copystat(src_path + path, dst_path + path)
    shutil.copy2(osp.join(src_path, sub_path), osp.join(dst_path, sub_path))
