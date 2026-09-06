PY ?= python3

.PHONY: install test lint fixtures blender-verify gate

install:
	$(PY) -m pip install -e "core[dev]"

test:
	cd core && $(PY) -m pytest tests

lint:
	$(PY) -m ruff check core/src core/tests addon/riggermortis_addon/bpy_bridge.py xtask/export_fixture_rigs.py

fixtures:
	$(PY) xtask/export_fixture_rigs.py

# Full Phase 0 gate against a real local Blender (needs `make install` first)
blender-verify:
	bash xtask/blender_verify.sh

gate: lint test blender-verify
	@echo "PHASE 0 GATE: PASS"
