PYTHON ?= python3

.PHONY: help test check package examples screenshots clean

help:
	@echo "make test         run the test suite"
	@echo "make check        validate the skill without building"
	@echo "make package      build dist/*.skill and the release zip"
	@echo "make examples     rebuild examples/*/dossier*.html"
	@echo "make screenshots  rebuild examples and docs/images (needs Playwright)"
	@echo "make clean        remove build output"

test:
	$(PYTHON) -m unittest discover -s tests -v

check:
	$(PYTHON) tools/package_skill.py --check

package: test
	$(PYTHON) tools/package_skill.py

examples:
	$(PYTHON) tools/build_examples.py

screenshots:
	$(PYTHON) tools/build_examples.py --screenshots

clean:
	rm -rf dist
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
