#!/bin/bash

if (( $# != 1 )); then
    echo "Usage: $0 <python>"
    exit 2
fi

PYTHON="$1"

# Idea from https://stackoverflow.com/a/21282690
if "$PYTHON" -c "import sys; print sys.version" | grep -q Anaconda; then
    echo "Error: it looks like you are using Anaconda."
    echo "This project does not work with Anaconda. Please try running:"
    echo "    make 'PYTHON=/path/to/alternate/python2.7'"
    echo "instead."
    exit 1
fi

