# Release Tag Script Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Node-based release tag script that fetches remote tags, bumps semantic versions, creates a new tag locally, and pushes it to `origin`.

**Architecture:** Create a standalone ESM script under `scripts/` that wraps `git` commands and exports pure helper functions for version parsing and bumping. Cover the helper behavior with Node's built-in test runner and document the usage in the README.

**Tech Stack:** Node.js ESM, git CLI, node:test

---
