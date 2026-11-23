.PHONY: check lint test

check: lint test

lint:
	bash -n bootstrap.sh scripts/*.sh
	zsh -n shell/zshrc shell/languages/*.zsh shell/tools/*.zsh profiles/default/zshrc
	python3 -B -m py_compile scripts/read-config.py tests/smoke_test.py

test:
	python3 -B tests/smoke_test.py
