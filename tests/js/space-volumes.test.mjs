import test from 'node:test';
import assert from 'node:assert/strict';
import { buildComparisonGeometry, categoryOpacity } from '../../api/app/static/js/space-volumes.js';

test('category opacity fades smoothly as the camera approaches', () => {
  assert.equal(categoryOpacity(1, 1000), 0.14);
  assert.equal(categoryOpacity(1, 0), 0.015);
  assert.equal(categoryOpacity(2, 1000), 0.11);
  assert.equal(categoryOpacity(2, 0), 0.01);
  assert.ok(categoryOpacity(1, 40) > categoryOpacity(1, 20));
  assert.ok(categoryOpacity(2, 40) > categoryOpacity(2, 20));
  for (const level of [1, 2]) {
    for (const distance of [-10, 0, 50, 100, 500, Infinity, NaN]) {
      const opacity = categoryOpacity(level, distance);
      assert.ok(Number.isFinite(opacity) && opacity >= 0 && opacity <= 0.14);
    }
  }
});

test('comparison geometry builds one minimum tree across all time clusters', () => {
  const points = [
    {observation_id: 'a', fetch_ts: '2026-10-01T00:00:00Z'},
    {observation_id: 'b', fetch_ts: '2026-10-01T12:00:00Z'},
    {observation_id: 'c', fetch_ts: '2026-10-03T00:00:00Z'},
    {observation_id: 'd', fetch_ts: '2026-10-03T12:00:00Z'},
  ];
  const positions = {a: [0, 0, 0], b: [3, 0, 0], c: [3, 4, 0], d: [10, 4, 0]};
  const snapshot = JSON.stringify(points);
  const geometry = buildComparisonGeometry(points, point => positions[point.observation_id]);
  assert.equal(geometry.clusters.length, 2);
  assert.deepEqual(geometry.clusters[0].center, [1.5, 0, 0]);
  assert.equal(geometry.clusters[0].count, 2);
  assert.equal(geometry.treeLines.length, points.length - 1);
  assert.equal(Object.hasOwn(geometry, 'lines'), false);
  assert.deepEqual(geometry.treeLines, [
    {from: [0, 0, 0], to: [3, 0, 0]},
    {from: [3, 0, 0], to: [3, 4, 0]},
    {from: [3, 4, 0], to: [10, 4, 0]},
  ]);
  assert.ok(geometry.clusters.every(cluster => cluster.radii.every(Number.isFinite)));
  assert.equal(JSON.stringify(points), snapshot);
});

test('comparison geometry includes observations exactly 24 hours apart', () => {
  const points = [
    {observation_id: 'a', fetch_ts: '2026-10-01T00:00:00Z'},
    {observation_id: 'b', fetch_ts: '2026-10-02T00:00:00Z'},
  ];
  const geometry = buildComparisonGeometry(points, point => point.observation_id === 'a' ? [0, 0, 0] : [4, 0, 24]);
  assert.equal(geometry.clusters.length, 1);
  assert.equal(geometry.clusters[0].count, 2);
  assert.equal(geometry.treeLines.length, 1);
});

test('comparison geometry excludes invalid times and positions', () => {
  const points = [
    {observation_id: 'invalid', fetch_ts: 'not-a-time'},
    {observation_id: 'missing-position', fetch_ts: '2026-10-01T00:00:00Z'},
    {observation_id: 'valid', fetch_ts: '2026-10-01T01:00:00Z'},
  ];
  const positions = {valid: [3, 4, 5]};
  const geometry = buildComparisonGeometry(points, point => positions[point.observation_id]);
  assert.equal(geometry.clusters.length, 1);
  assert.equal(geometry.clusters[0].count, 1);
  assert.deepEqual(geometry.clusters[0].center, [3, 4, 5]);
  assert.deepEqual(geometry.treeLines, []);
});

test('single-point comparison clusters have finite display radii', () => {
  const geometry = buildComparisonGeometry(
    [{observation_id: 'a', fetch_ts: '2026-10-01T00:00:00Z'}],
    () => [3, 4, 5],
  );
  assert.deepEqual(geometry.clusters[0].radii, [2, 2, 2]);
  assert.deepEqual(geometry.treeLines, []);
  assert.deepEqual(buildComparisonGeometry([], () => [0, 0, 0]), {clusters: [], treeLines: []});
});

test('comparison geometry supports flattened 2D coordinates', () => {
  const points = ['a', 'b', 'c'].map(observation_id => ({observation_id, fetch_ts: '2026-10-01T00:00:00Z'}));
  const positions = {a: [0, 0, 0], b: [3, 0, 0], c: [3, 4, 0]};
  const geometry = buildComparisonGeometry(points, point => positions[point.observation_id]);
  assert.deepEqual(geometry.treeLines, [
    {from: [0, 0, 0], to: [3, 0, 0]},
    {from: [3, 0, 0], to: [3, 4, 0]},
  ]);
});

test('comparison geometry skips zero-length edges without changing the input', () => {
  const points = ['a', 'b', 'c'].map(observation_id => ({observation_id, fetch_ts: '2026-10-01T00:00:00Z'}));
  const positions = {a: [0, 0, 0], b: [0, 0, 0], c: [3, 0, 0]};
  const geometry = buildComparisonGeometry(points, point => positions[point.observation_id]);
  assert.equal(geometry.treeLines.length, 2);
  assert.ok(geometry.treeLines.every(line => Math.hypot(...line.from.map((value, axis) => line.to[axis] - value)) > 0));
});
