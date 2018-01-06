#!/bin/bash

# See
#     https://stackoverflow.com/a/3464399
#for some more sophisticated ideas for this.

MY_DIR="$(dirname "$(readlink -e "$0")")"
cd "$MY_DIR"/..

# TODO: Make this idempotent. If link already exists and has correct target,
# then silently pass.
if ! ln -s ../../hooks/pre-commit .git/hooks/pre-commit; then
    echo
    echo "** Failed to create link. Aborting. **"
    exit 1
fi
