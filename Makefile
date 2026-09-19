.PHONY: build check deploy deploy-dry serve help

# --- deploy to the edge ---------------------------------------------------
# Same Akamai/Linode node as chernov.ca, provisioned in dk-semantic-backend-host.
# Caddy there serves $(REMOTE_ROOT) for portfolio.chernov.ca.
#
# This target publishes files and nothing else. It does not touch Caddy, DNS,
# or any other site's directory -- REMOTE_ROOT is asserted to be exactly one
# level under /var/www before rsync --delete is allowed anywhere near it.
EDGE        ?= root@172.105.24.72
SITE        ?= portfolio-chernov
DIST        ?= docs
REMOTE_ROOT ?= /var/www/$(SITE)

RSYNC_FLAGS := -az --delete --chmod=D755,F644 --exclude .git --exclude .keep

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-12s\033[0m %s\n", $$1, $$2}'

build: ## Render content/*.json into docs/index.html
	@python3 build.py

serve: build ## Build, then serve docs/ on http://127.0.0.1:8000
	@cd $(DIST) && python3 -m http.server 8000 --bind 127.0.0.1

check: ## Verify the payload before anything leaves this machine
	@echo "$(REMOTE_ROOT)" | grep -qE '^/var/www/[A-Za-z0-9._-]+$$' \
		|| { echo "refusing: unsafe REMOTE_ROOT=$(REMOTE_ROOT)"; exit 1; }
	@test -f "$(DIST)/index.html" \
		|| { echo "refusing: no $(DIST)/index.html -- wrong DIST, or nothing built"; exit 1; }
	@test -f "$(DIST)/CNAME" \
		|| { echo "refusing: no $(DIST)/CNAME -- GitHub Pages would drop the domain"; exit 1; }

deploy: build ## Build and publish to the edge
	@$(MAKE) check
	@ssh $(EDGE) 'mkdir -p $(REMOTE_ROOT)'
	rsync $(RSYNC_FLAGS) "$(DIST)/" "$(EDGE):$(REMOTE_ROOT)/"
	@# Provenance, written after the sync because rsync --delete would remove it.
	@# `dirty=YES` says it was published from a tree with uncommitted changes.
	@printf 'site=%s\nrepo=%s\ncommit=%s\nbranch=%s\ndirty=%s\nbuilt=%s\nfrom=%s\n' \
		"$(SITE)" "$$(basename $$(git rev-parse --show-toplevel))" \
		"$$(git rev-parse --short HEAD)" "$$(git rev-parse --abbrev-ref HEAD)" \
		"$$(test -z "$$(git status --porcelain)" && echo no || echo YES)" \
		"$$(date -Is)" "$$(hostname -s)" \
		| ssh $(EDGE) 'cat > $(REMOTE_ROOT)/DEPLOYED'
	@echo "deployed $(SITE) -> $(EDGE):$(REMOTE_ROOT)"

deploy-dry: build ## Show what deploy would change; transfer nothing
	@$(MAKE) check
	@rsync $(RSYNC_FLAGS) -n --itemize-changes "$(DIST)/" "$(EDGE):$(REMOTE_ROOT)/"
