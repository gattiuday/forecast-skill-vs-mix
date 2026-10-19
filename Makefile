PY ?= python3
export PYTHONPATH := $(CURDIR)/src:$(CURDIR)/experiments

.PHONY: help install lint test experiments receipts fixture verify clean

help:
	@echo "install      install the package and development dependencies"
	@echo "lint         ruff check and format check"
	@echo "test         pytest with coverage and machine readable reports"
	@echo "experiments  re-run all six experiments into docs/experiments/"
	@echo "receipts     re-measure every published figure and check the prose"
	@echo "fixture      regenerate the committed demand panel"
	@echo "verify       lint, test, receipts. The one command the README promises."

install:
	$(PY) -m pip install -e ".[dev]"

lint:
	ruff check src tests experiments tools
	ruff format --check src tests experiments tools

test:
	$(PY) -m pytest tests/ -q --junitxml=junit.xml --cov=fsvm --cov-report=json --cov-report=term

experiments:
	@for e in experiments/exp*.py; do echo "== $$e"; $(PY) $$e; done

fixture:
	$(PY) -m fsvm.cli generate --out data/fixtures/panel-realistic.csv --scenario realistic

receipts:
	$(PY) tools/capture_evidence.py
	$(PY) tools/collect_metrics.py --skip-tests
	$(PY) tools/check_numbers.py

verify: lint test receipts

clean:
	rm -rf .pytest_cache .ruff_cache junit.xml coverage.json .coverage

.PHONY: evidence diagram
evidence:
	$(PY) tools/capture_evidence.py

diagram:
	$(PY) tools/render_diagram.py
