.PHONY: check
check:
	@command -v uv >/dev/null 2>&1 || { echo "uv not found"; exit 1; }
	@command -v asciinema >/dev/null 2>&1 || { echo "asciinema not found (need >= 3.0)"; exit 1; }
	@asciinema --version
	@echo "dependencies OK"
