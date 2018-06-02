#!/bin/bash

# See
#     https://stackoverflow.com/a/3464399
#for some more sophisticated ideas for this.

MY_DIR="$(dirname "$(readlink -e "$0")")"
cd "$MY_DIR"/..

# LINK_TARGET is relative to the LINK's dir, so that we can run
#     ln -s "$LINK_TARGET" "$LINK"
LINK=.git/hooks/pre-commit
LINK_TARGET=../../hooks/pre-commit

# If LINK is a symlink and LINK is the same file as LINK_TARGET, then figure
# LINK already points to LINK_TARGET. Technically it's also possible that
# they're both symlinks to some third file, but it doesn't actually matter;
# relinking LINK to LINK_TARGET wouldn't change that.
#
# Note: it's tempting to write:
#     [ "$LINK" -ef "$LINK_TARGET" ]
# for the second clause. But that's wrong, because LINK_TARGET is relative to
# the link's directory, not our own. Specifically, the link goes in:
#     {repo}/.git/hooks/pre-commit
# so when we point it to ../../hooks/pre-commit, that really means:
#     {repo}/.git/hooks/../../hooks/pre-commit
# AKA
#     {repo}/hooks/pre-commit
# But the script runs from {repo}. So if we compare LINK to LINK_TARGET
# directly, then we're comparing the link to the path:
#     {repo}/../../hooks/pre-commit
# which is a (probably) non-existent file outside of the git repository. The
# solution is to use `dirname "$LINK"` to evaluate the LINK_TARGET relative to
# the directory containing the LINK.
if [ -L "$LINK" ] && [ "$LINK" -ef "$(dirname "$LINK")"/"$LINK_TARGET" ]; then
    # In this case do nothing (successfully), so that people can run this
    # script multiple times without getting errors.
    echo "Pre-commit hook already linked."
else
    if ! (
            ln -s "$LINK_TARGET" "$LINK" &&
            echo -e '\nCreated pre-commit hook'
        ); then
        echo
        echo "** Failed to create link. Aborting. **"
        exit 1
    fi
fi
