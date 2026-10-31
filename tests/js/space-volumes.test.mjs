import test from 'node:test';
import assert from 'node:assert/strict';
import { buildComparisonGeometry, categoryOpacity, comparisonCircleGeometry } from '../../api/app/static/js/space-volumes.js';

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

test('comparison circle contains projected points on the camera-facing Z plane', () => {
  const points = [[0, 0, 0], [10, 0, 10], [0, 10, 5], [-4, 2, 8]];
  const circle = comparisonCircleGeometry(points, [1, 1, 0]);
  assert.deepEqual(circle.center, [3, 5, 5]);
  assert.ok(Math.abs(Math.hypot(...circle.horizontal) - 1) < 1e-10);
  assert.equal(circle.horizontal[2], undefined);
  for (const point of points) {
    const relative = point.map((value, index) => value - circle.center[index]);
    const horizontal = relative[0] * circle.horizontal[0] + relative[1] * circle.horizontal[1];
    const distance = Math.hypot(horizontal, relative[2]);
    assert.ok(distance <= circle.radius + 1e-10, `${distance} > ${circle.radius}`);
  }
  assert.ok(circle.radius >= 2);
});

test('coincident and degenerate circles have stable finite bounds', () => {
  const circle = comparisonCircleGeometry([[2, 3, 4], [2, 3, 4]], [0, 0, 9]);
  assert.deepEqual(circle.center, [2, 3, 4]);
  assert.deepEqual(circle.horizontal, [1, 0]);
  assert.equal(circle.radius, 2);
  assert.equal(comparisonCircleGeometry([], [1, 0, 0]), null);
  assert.equal(comparisonCircleGeometry([[NaN, 0, 0]], [1, 0, 0]), null);
});

test('comparison geometry groups nearby times and connects adjacent clusters', () => {
  const points = [
    {observation_id: 'a', fetch_ts: '2026-10-01T00:00:00Z'},
    {observation_id: 'b', fetch_ts: '2026-10-01T12:00:00Z'},
    {observation_id: 'c', fetch_ts: '2026-10-03T00:00:00Z'},
  ];
  const positions = {a: [0, 0, 0], b: [2, 4, 6], c: [20, 20, 30]};
  const geometry = buildComparisonGeometry(points, point => positions[point.observation_id]);
  assert.equal(geometry.clusters.length, 2);
  assert.deepEqual(geometry.clusters[0].center, [1, 2, 3]);
  assert.deepEqual(geometry.clusters[0].radii, [2, 2, 3]);
  assert.equal(geometry.clusters[0].count, 2);
  assert.deepEqual(geometry.lines, [{from: [1, 2, 3], to: [20, 20, 30]}]);
  assert.ok(geometry.clusters.every(cluster => cluster.radii.every(Number.isFinite)));
});

test('comparison geometry includes observations exactly 24 hours apart', () => {
  const points = [
    {observation_id: 'a', fetch_ts: '2026-10-01T00:00:00Z'},
    {observation_id: 'b', fetch_ts: '2026-10-02T00:00:00Z'},
  ];
  const geometry = buildComparisonGeometry(points, point => point.observation_id === 'a' ? [0, 0, 0] : [4, 0, 24]);
  assert.equal(geometry.clusters.length, 1);
  assert.equal(geometry.clusters[0].count, 2);
  assert.deepEqual(geometry.lines, []);
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
});

test('single-point comparison clusters have finite display radii', () => {
  const geometry = buildComparisonGeometry(
    [{observation_id: 'a', fetch_ts: '2026-10-01T00:00:00Z'}],
    () => [3, 4, 5],
  );
  assert.deepEqual(geometry.clusters[0].radii, [2, 2, 2]);
  assert.deepEqual(buildComparisonGeometry([], () => [0, 0, 0]), {clusters: [], lines: []});
});
