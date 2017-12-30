.PHONY: all smush clean simplify

# To use a Python binary other than the one in your PATH, run
#     make 'PYTHON=/path/to/alternate/python2.7'
PYTHON ?= python2.7

VIRTUALENV = ./venv
BUILDFILES = build-resources

all: smush

# .PHONY-ness of smush matters, because there actually is a file "smush" (which
# is not rebuilt by "make smush").
smush: Makefile $(BUILDFILES)/requirements.txt
	virtualenv "-p$(PYTHON)" $(VIRTUALENV)
	bash -c 'source $(VIRTUALENV)/bin/activate; pip install -r $(BUILDFILES)/requirements.txt'

# NOTE: In WaRTS, we also needed to do this as part of "make smush"; it was
# necessary so that you can import certain panda3d modules. However, now that
# Panda3D has proper virtualenv support, I'm hoping it won't be necessary. So
# comment it out until/unless we find we need it.
# 	cp $(BUILDFILES)/panda3d.pth $(VIRTUALENV)/lib/python2.7/site-packages/

simplify:
	find src -name '*.pyc' -exec echo removing '{}' ';' \
	                       -exec rm -f '{}' ';'

clean: simplify
	rm -rf $(VIRTUALENV)

# TODO: Once we get tests working, replace the simplify/clean rules with these:

# simplify:
# 	rm -rf tests/__pycache__
# 	find src tests -name '*.pyc' -exec echo removing '{}' ';' \
# 	                             -exec rm -f '{}' ';'
# 
# clean: simplify
# 	rm -rf $(VIRTUALENV)
# 	rm -rf .tox .cache
