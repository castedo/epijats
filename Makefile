all:
	@echo Nope

test:
	python -Wdefault -m pytest

.PHONY: all test
