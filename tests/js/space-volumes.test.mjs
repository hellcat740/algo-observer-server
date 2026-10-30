import test from 'node:test';
import assert from 'node:assert/strict';
import { categoryOpacity, comparisonCircleGeometry } from '../../api/app/static/js/space-volumes.js';

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
