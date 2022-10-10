import os

def up_to_date(target, source):
    last_update = os.path.getmtime(target) if target.exists() else 0
    return last_update > os.path.getmtime(source)
