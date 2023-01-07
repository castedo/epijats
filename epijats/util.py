import os, shutil, tempfile


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


def swhid_from_files(path):
    import git

    if not path.is_dir():
        return "swh:1:cnt:" + git.Git().hash_object(path)
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = git.Repo.init(tmpdir)
        g = git.Git(path)  # path is working dir
        g.set_persistent_git_options(git_dir=repo.git_dir)
        g.add(".")
        return "swh:1:dir:" + g.write_tree()
