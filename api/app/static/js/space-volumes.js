export function categoryOpacity(level, distance) {
  const [near, far] = level === 1 ? [0.015, 0.14] : [0.01, 0.11];
  const measured = Number.isFinite(distance) ? Math.max(0, distance) : 240;
  const progress = Math.min(1, Math.max(0, (measured - 35) / 205));
  return near + (far - near) * progress;
}

export function buildComparisonGeometry(points, positionFor, thresholdHours = 24) {
  const sorted = (points || []).map(point => ({point, time: Date.parse(point.fetch_ts)}))
    .filter(item => Number.isFinite(item.time))
    .sort((a, b) => a.time - b.time || String(a.point.observation_id).localeCompare(String(b.point.observation_id)));
  const groups = [];
  for (const item of sorted) {
    const previous = groups.at(-1);
    if (!previous || item.time - previous.lastTime > thresholdHours * 3600000) {
      groups.push({items: [], lastTime: item.time});
    }
    const group = groups.at(-1);
    group.items.push(item.point);
    group.lastTime = item.time;
  }
  const clusters = groups.map((group, index) => {
    const positioned = group.items.map(point => ({point, position: positionFor(point)}))
      .filter(item => Array.isArray(item.position) && item.position.length >= 3 && item.position.every(Number.isFinite));
    if (!positioned.length) return null;
    const center = [0, 1, 2].map(axis => {
      const values = positioned.map(item => item.position[axis]);
      return (Math.min(...values) + Math.max(...values)) / 2;
    });
    const radii = [0, 1, 2].map(axis => {
      const values = positioned.map(item => item.position[axis]);
      return Math.max(2, (Math.max(...values) - Math.min(...values)) / 2);
    });
    return {key: `cluster-${index}`, center, radii, count: positioned.length};
  }).filter(Boolean);
  const lines = clusters.slice(1).map((cluster, index) => ({from: clusters[index].center, to: cluster.center}));
  return {clusters, lines};
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
