import test from 'node:test';
import assert from 'node:assert/strict';
import { clamp, pointerTilt, damp } from '../../api/app/static/js/balance-math.js';

test('pointer tilt is bounded and centered', () => {
  assert.deepEqual(pointerTilt(500, 500, 1000, 1000), { beam: 0, pitch: 0 });
  assert.equal(pointerTilt(-100, 500, 1000, 1000).beam, -6 * Math.PI / 180);
  assert.equal(pointerTilt(1100, 500, 1000, 1000).beam, 6 * Math.PI / 180);
});

test('damping is frame-rate safe and clamp bounds values', () => {
  assert.equal(clamp(4, 0, 2), 2);
  assert.equal(damp(0, 1, 8, 0), 0);
  assert.ok(damp(0, 1, 8, 1 / 60) > 0);
  assert.ok(damp(0, 1, 8, 1 / 60) < 1);
});
