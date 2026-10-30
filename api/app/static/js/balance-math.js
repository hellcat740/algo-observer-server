export const clamp = (value, min, max) => Math.min(max, Math.max(min, value));

export function pointerTilt(x, y, width, height) {
  const nx = clamp((x / Math.max(1, width) - 0.5) * 2, -1, 1);
  const ny = clamp((y / Math.max(1, height) - 0.5) * 2, -1, 1);
  return { beam: nx * 6 * Math.PI / 180, pitch: ny * 1.5 * Math.PI / 180 };
}

export function damp(current, target, lambda, deltaSeconds) {
  return current + (target - current) * (1 - Math.exp(-lambda * Math.max(0, deltaSeconds)));
}
