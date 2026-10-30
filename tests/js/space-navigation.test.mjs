import test from 'node:test';
import assert from 'node:assert/strict';
import { movementVector } from '../../api/app/static/js/space-navigation.js';

const close = (actual, expected) => actual.forEach((value, index) => assert.ok(Math.abs(value - expected[index]) < 1e-9));

test('neutral and degenerate movement stay at zero', () => {
  assert.deepEqual(movementVector(new Set(), [0, -1], [1, 0], 20, 0.1), [0, 0]);
  assert.deepEqual(movementVector(new Set(['w']), [0, 0], [1, 0], 20, 0.1), [0, 0]);
  assert.deepEqual(movementVector(new Set(['d']), [0, -1], [0, 0], 20, 0.1), [0, 0]);
});

test('W and S move along normalized forward XY', () => {
  close(movementVector(new Set(['w']), [0, -2], [1, 0], 20, 0.1), [0, -2]);
  close(movementVector(new Set(['s']), [0, -2], [1, 0], 20, 0.1), [0, 2]);
});

test('A and D move along normalized right XY', () => {
  close(movementVector(new Set(['d']), [0, -1], [2, 0], 20, 0.1), [2, 0]);
  close(movementVector(new Set(['a']), [0, -1], [2, 0], 20, 0.1), [-2, 0]);
});

test('diagonal movement is normalized and frame-time scaled', () => {
  close(movementVector(new Set(['w', 'd']), [0, -1], [1, 0], 20, 0.5), [Math.SQRT1_2 * 10, -Math.SQRT1_2 * 10]);
});
