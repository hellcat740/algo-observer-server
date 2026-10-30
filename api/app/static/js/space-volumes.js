export function categoryOpacity(level, distance) {
  const [near, far] = level === 1 ? [0.015, 0.14] : [0.01, 0.11];
  const measured = Number.isFinite(distance) ? Math.max(0, distance) : 240;
  const progress = Math.min(1, Math.max(0, (measured - 35) / 205));
  return near + (far - near) * progress;
}

export function comparisonCircleGeometry(points, cameraRight) {
  const valid = (points || []).filter(point => Array.isArray(point) && point.length >= 3 && point.slice(0, 3).every(Number.isFinite));
  if (!valid.length || valid.length !== (points || []).length) return null;
  const center = [0, 1, 2].map(axis => {
    const values = valid.map(point => point[axis]);
    return (Math.min(...values) + Math.max(...values)) / 2;
  });
  const length = Math.hypot(cameraRight?.[0] || 0, cameraRight?.[1] || 0);
  const horizontal = length > 1e-10 ? [cameraRight[0] / length, cameraRight[1] / length] : [1, 0];
  const radius = Math.max(2, ...valid.map(point => {
    const relative = point.map((value, index) => value - center[index]);
    return Math.hypot(relative[0] * horizontal[0] + relative[1] * horizontal[1], relative[2]) + 1;
  }));
  return {center, radius, horizontal};
}
