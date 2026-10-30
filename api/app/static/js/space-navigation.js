function normalized(vector) {
  const length = Math.hypot(vector[0] || 0, vector[1] || 0);
  return length > 1e-9 ? [vector[0] / length, vector[1] / length] : [0, 0];
}

export function movementVector(keys, forward, right, speed, deltaSeconds) {
  const ahead = normalized(forward);
  const sideways = normalized(right);
  let x = 0;
  let y = 0;
  if (keys.has('w')) { x += ahead[0]; y += ahead[1]; }
  if (keys.has('s')) { x -= ahead[0]; y -= ahead[1]; }
  if (keys.has('d')) { x += sideways[0]; y += sideways[1]; }
  if (keys.has('a')) { x -= sideways[0]; y -= sideways[1]; }
  const length = Math.hypot(x, y);
  if (!length) return [0, 0];
  const scale = Math.max(0, Number(speed) || 0) * Math.max(0, Number(deltaSeconds) || 0) / length;
  return [x * scale, y * scale];
}
