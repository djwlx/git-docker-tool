#!/usr/bin/env node

import process from 'node:process';
import { execFileSync } from 'node:child_process';
import { pathToFileURL } from 'node:url';

const VALID_BUMP_TYPES = new Set(['major', 'minor', 'patch']);
const VERSION_TAG_PATTERN = /^v(\d+)\.(\d+)\.(\d+)$/;

export function normalizeBumpType(rawValue) {
  const value = rawValue ?? 'patch';
  if (!VALID_BUMP_TYPES.has(value)) {
    throw new Error(`Unsupported bump type "${value}". Use major, minor, or patch.`);
  }
  return value;
}

export function selectLatestVersionTag(tags) {
  const parsedTags = tags
    .map((tag) => {
      const match = VERSION_TAG_PATTERN.exec(tag);
      if (!match) {
        return null;
      }

      return {
        tag,
        major: Number.parseInt(match[1], 10),
        minor: Number.parseInt(match[2], 10),
        patch: Number.parseInt(match[3], 10),
      };
    })
    .filter(Boolean);

  if (parsedTags.length === 0) {
    return null;
  }

  parsedTags.sort((left, right) => {
    if (left.major !== right.major) {
      return right.major - left.major;
    }
    if (left.minor !== right.minor) {
      return right.minor - left.minor;
    }
    return right.patch - left.patch;
  });

  return parsedTags[0].tag;
}

export function bumpVersion(currentTag, bumpType) {
  if (currentTag === null) {
    return 'v0.0.1';
  }

  const match = VERSION_TAG_PATTERN.exec(currentTag);
  if (!match) {
    throw new Error(`Invalid version tag "${currentTag}". Expected v<major>.<minor>.<patch>.`);
  }

  let major = Number.parseInt(match[1], 10);
  let minor = Number.parseInt(match[2], 10);
  let patch = Number.parseInt(match[3], 10);

  switch (bumpType) {
    case 'major':
      major += 1;
      minor = 0;
      patch = 0;
      break;
    case 'minor':
      minor += 1;
      patch = 0;
      break;
    case 'patch':
      patch += 1;
      break;
    default:
      throw new Error(`Unsupported bump type "${bumpType}".`);
  }

  return `v${major}.${minor}.${patch}`;
}

export function isExecutedDirectly(scriptPath, importMetaUrl) {
  if (!scriptPath) {
    return false;
  }
  return pathToFileURL(scriptPath).href === importMetaUrl;
}

export function normalizeGitCommandOutput(output) {
  if (output === null || output === undefined) {
    return '';
  }
  return String(output).trim();
}

function runGit(args, options = {}) {
  const output = execFileSync('git', args, {
    cwd: options.cwd ?? process.cwd(),
    encoding: 'utf8',
    stdio: options.stdio ?? ['ignore', 'pipe', 'pipe'],
  });
  return normalizeGitCommandOutput(output);
}

function ensureCleanWorktree() {
  const output = runGit(['status', '--porcelain']);
  if (output !== '') {
    throw new Error('Working tree is not clean. Commit or stash changes before releasing.');
  }
}

function fetchRemoteTags() {
  runGit(['fetch', '--tags', 'origin'], { stdio: 'inherit' });
}

function getAllTags() {
  const output = runGit(['tag', '--list']);
  return output === '' ? [] : output.split(/\r?\n/).filter(Boolean);
}

function createTag(tag) {
  runGit(['tag', tag], { stdio: 'inherit' });
}

function pushTag(tag) {
  runGit(['push', 'origin', tag], { stdio: 'inherit' });
}

function main() {
  const bumpType = normalizeBumpType(process.argv[2]);

  ensureCleanWorktree();
  fetchRemoteTags();

  const currentTag = selectLatestVersionTag(getAllTags());
  const nextTag = bumpVersion(currentTag, bumpType);

  console.log(`Current version: ${currentTag ?? '(none)'}`);
  console.log(`Next version: ${nextTag}`);

  createTag(nextTag);
  pushTag(nextTag);

  console.log(`Released ${nextTag}`);
}

if (isExecutedDirectly(process.argv[1], import.meta.url)) {
  try {
    main();
  } catch (error) {
    console.error(error instanceof Error ? error.message : String(error));
    process.exitCode = 1;
  }
}
