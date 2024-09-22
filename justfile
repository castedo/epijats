all:
	@echo Nope

test:
	python3 -Wdefault -m pytest

dist:
	python3 -m build

clean:
	rm -rf dist
	rm -rf epijats.egg-info
