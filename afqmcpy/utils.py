import subprocess
import sys

def get_git_revision_hash():
    '''Return git revision.

    Adapted from: http://stackoverflow.com/questions/14989858/get-the-current-git-hash-in-a-python-script

Returns
-------
sha1 : string
    git hash with -dirty appended if uncommitted changes.
'''

    src = sys.path[0]

    sha1 = subprocess.check_output(['git', 'rev-parse', 'HEAD'],
                                   cwd=src).strip()
    suffix = subprocess.check_output(['git', 'status',
                                     '--porcelain',
                                     '../afqmcpy'],
                                     cwd=src).strip()
    if suffix:
        return sha1 + '-dirty'
    else:
        return sha1
