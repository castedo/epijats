import os, shutil, sys, subprocess


def up_to_date(target, source):
    last_update = os.path.getmtime(target) if target.exists() else 0
    return last_update > os.path.getmtime(source)


def copytree_nostat(src, dst):
    """like shutil but avoids calling copystat so SELinux context is not copied"""

    os.makedirs(dst, exist_ok=True)
    for srcentry in os.scandir(src):
        dstentry = os.path.join(dst, srcentry.name)
        if srcentry.is_dir():
            copytree_nostat(srcentry, dstentry)
        else:
            shutil.copy(srcentry, dstentry)
    return dst


def git_hash_object(path):
    ret = subprocess.run(['git', 'hash-object', path],
        check=True, text=True, stdout=subprocess.PIPE, stderr=sys.stderr)
    return ret.stdout.rstrip()
