TEST_OPTIONS=-m unittest discover --start-directory tests --top-level-directory .
CPU_COUNT=$(shell python3 -c "from multiprocessing import cpu_count; print(cpu_count())")

help:
	@echo "Please use \`make <target>' where <target> is one of:"
	@echo "  help           to show this message"
	@echo "  all            to to execute all following targets (except \`test')"
	@echo "  dist           to generate installable Python packages"
	@echo "  dist-clean     to remove generated Python packages"
	@echo "  docs-clean     to remove documentation"
	@echo "  docs-html      to generate HTML documentation"
	@echo "  docs-tests     to (re)generate .rst files for the tests"
	@echo "  install-dev    to install in editable mode with development dependencies"
	@echo "  lint           to run all linters"
	@echo "  lint-flake8    to run the flake8 linter"
	@echo "  lint-pylint    to run the pylint linter"
	@echo "  publish        to upload dist/* to PyPi"

# Edit with caution! Travis CI uses this target. ¶ We run docs-clean before
# docs-html to ensure a complete build. (Warnings are emitted only when a file
# is compiled, and Sphinx does not needlessly recompile.) More broadly, we
# order dependencies by execution time and (anecdotal) likelihood of finding
# issues.
all: dist-clean lint docs-clean docs-html dist

dist:
	./setup.py --quiet sdist bdist_wheel --universal

dist-clean:
	rm -rf build dist pulp_2_tests.egg-info

docs-clean:
	@cd docs; $(MAKE) clean

docs-html: docs-tests
	@cd docs; $(MAKE) html

docs-tests:
	rm -rf docs/tests/*
	scripts/gen_docs_tests.sh

install-dev:
	pip install -q -e .[dev]

lint: lint-flake8 lint-pylint

# E501 and F401 are ignored because Pylint performs similar checks.
lint-flake8:
	flake8 . --ignore E501,F401 --exclude docs/_build,build

# Pulp 2 Test depends on Pulp Smash, and Pulp Smash should be considered a third
# party library. It appears that when this dependency is satisfied by a local
# clone of the Pulp Smash repository, pylint will conclude that Pulp Smash is
# not a third party library.
lint-pylint:
	pylint -j $(CPU_COUNT) --reports=n --disable=I,wrong-import-order \
		docs/conf.py \
		pulp_2_tests \
		setup.py

publish: dist
	twine upload dist/*

.PHONY: help all dist-clean docs-clean docs-html docs-tests lint lint-flake8 \
    lint-pylint publish install-dev
