SHELL := /bin/bash
COMPOSE := docker compose -f docker-compose.yml

.PHONY: run run-live gpu-up verify eval eval-live bench record-fixtures record-live test test-code test-ui report down clean

run:            ## Judges: build, verify replay outputs, start the app on http://localhost:8080
	@test -f .env || cp .env.example .env
	$(COMPOSE) build app
	$(COMPOSE) run --rm app python -m briefklar.verify --replay data/replay --bench data/bench_small
	$(COMPOSE) up app

run-live:       ## Use a live endpoint: LLM_BASE_URL must be set in .env
	BRIEFKLAR_MODE=live $(COMPOSE) up app

gpu-up:         ## Air-gapped/on-prem: start local vLLM + app (needs NVIDIA GPU)
	BRIEFKLAR_MODE=live $(COMPOSE) --profile gpu up

verify:         ## Re-run the deterministic parts on cached outputs and compare with the committed summary
	$(COMPOSE) run --rm app python -m briefklar.verify --replay data/replay --bench data/bench_small

eval:           ## Recompute all metrics from cached responses (no GPU)
	$(COMPOSE) run --rm app python -m bench.eval.run --mode replay

eval-live:      ## Re-run all systems against LLM_BASE_URL / JUDGE_BASE_URL
	$(COMPOSE) run --rm app python -m bench.eval.run --mode live

bench:          ## Regenerate the synthetic letters and gold (then record responses again)
	$(COMPOSE) run --rm app python -m bench.generator.build --seed 7

record-fixtures: ## Fill data/replay with FIXTURE responses (no model). Stand-in until record-live has run
	$(COMPOSE) run --rm -e BRIEFKLAR_MODE=live app python -m bench.fixtures.record

record-live:    ## Fill data/replay with real responses from LLM_BASE_URL (needs Apertus)
	$(COMPOSE) run --rm -e BRIEFKLAR_MODE=live app python -m bench.fixtures.record --live

test:           ## Everything, including the checks that fail until official sources are filled in
	$(COMPOSE) run --rm app pytest -q -p no:cacheprovider

test-code:      ## Code tests only (leaves out the open source-required items)
	$(COMPOSE) run --rm app pytest -q -p no:cacheprovider -m "not source_required"

test-ui:        ## Browser tests: keyboard path, accessibility scan, RTL and Tigrinya (needs node + uv locally)
	cd frontend && npm ci && npx playwright install chromium && npm run build && npx playwright test

report:         ## technical_report.md -> PDF (rename to <TeamName>_Report.pdf before submitting)
	$(COMPOSE) run --rm -v $(CURDIR):/work app python -m briefklar.render.report /work/technical_report.md /work/TeamName_Report.pdf

down:
	$(COMPOSE) down -v

clean: down
	rm -rf frontend/build frontend/.svelte-kit frontend/test-results bench/out
