# Standalone Compose For Configs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a standalone Docker Compose file under the configs repository for deploying `djwl/git-docker-tool:latest` without coupling it to the existing aggregate compose entrypoint.

**Architecture:** Create one self-contained compose file in `configs/docker` that reuses `./.env`, mounts the configs repository root into `/workspace`, and points `COMPOSE_ROOT` at `/workspace/docker`. Keep service-specific settings overridable through optional environment variables with sensible defaults so deployment works immediately.

**Tech Stack:** Docker Compose YAML, existing `.env` conventions

---

### Task 1: Add standalone deployment compose

**Files:**
- Create: `C:/Users/16029/Code/configs/docker/git-docker-tool-compose.yaml`

- [ ] **Step 1: Write the compose file**

```yaml
name: git-docker-tool

services:
  git-docker-tool:
    image: djwl/git-docker-tool:latest
    container_name: git-docker-tool
    restart: unless-stopped
    env_file:
      - ./.env
    environment:
      TZ: ${TZ}
      TTYD_CREDENTIALS: ${GIT_DOCKER_TOOL_CREDENTIALS:-admin:adminadmin}
      COMPOSE_ROOT: /workspace/docker
      PRUNE_INTERVAL_HOURS: ${GIT_DOCKER_TOOL_PRUNE_INTERVAL_HOURS:-24}
      MANAGEMENT_PORT: 7680
      TTYD_PORT: 7681
    ports:
      - ${GIT_DOCKER_TOOL_WEB_PORT:-7680}:7680
      - ${GIT_DOCKER_TOOL_TTYD_PORT:-7681}:7681
    volumes:
      - ../:/workspace
      - /var/run/docker.sock:/var/run/docker.sock
```

- [ ] **Step 2: Verify the file contents**

Run: `Get-Content C:\Users\16029\Code\configs\docker\git-docker-tool-compose.yaml`
Expected: the service points to `djwl/git-docker-tool:latest`, uses `env_file: ./.env`, mounts `../:/workspace`, and sets `COMPOSE_ROOT` to `/workspace/docker`

- [ ] **Step 3: Commit**

```bash
git -C C:/Users/16029/Code/configs add docker/git-docker-tool-compose.yaml
git -C C:/Users/16029/Code/configs commit -m "feat: add standalone git-docker-tool compose"
```
