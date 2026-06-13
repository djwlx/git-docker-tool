import test from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

import {
  bumpVersion,
  isExecutedDirectly,
  normalizeBumpType,
  selectLatestVersionTag,
} from '../scripts/release-tag.mjs';

test('normalizeBumpType defaults to patch', () => {
  assert.equal(normalizeBumpType(undefined), 'patch');
});

test('normalizeBumpType accepts major minor and patch', () => {
  assert.equal(normalizeBumpType('major'), 'major');
  assert.equal(normalizeBumpType('minor'), 'minor');
  assert.equal(normalizeBumpType('patch'), 'patch');
});

test('selectLatestVersionTag ignores non-semver tags', () => {
  assert.equal(selectLatestVersionTag(['foo', 'v1.2', 'v1.2.3', 'v0.9.9']), 'v1.2.3');
});

test('selectLatestVersionTag returns null when no version tags exist', () => {
  assert.equal(selectLatestVersionTag(['latest', 'test']), null);
});

test('bumpVersion increments patch by default', () => {
  assert.equal(bumpVersion('v0.0.4', 'patch'), 'v0.0.5');
});

test('bumpVersion increments minor and resets patch', () => {
  assert.equal(bumpVersion('v1.4.9', 'minor'), 'v1.5.0');
});

test('bumpVersion increments major and resets minor and patch', () => {
  assert.equal(bumpVersion('v1.4.9', 'major'), 'v2.0.0');
});

test('bumpVersion starts from v0.0.1 when no current tag exists', () => {
  assert.equal(bumpVersion(null, 'patch'), 'v0.0.1');
});

test('isExecutedDirectly matches Windows script paths', () => {
  const scriptPath = path.resolve('scripts/release-tag.mjs');
  const importMetaUrl = pathToFileURL(scriptPath).href;
  assert.equal(isExecutedDirectly(scriptPath, importMetaUrl), true);
});
