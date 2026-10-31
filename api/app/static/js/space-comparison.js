function validPoints(points) {
  return (points || []).filter(point => (
    point && Number.isFinite(point.normalized_price_cents) && point.normalized_price_cents >= 0
  )).slice().sort((a, b) => String(a.observation_id).localeCompare(String(b.observation_id)));
}

function median(values) {
  const sorted = values.slice().sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}

export function buildAnalyzableComparisonGroups(points) {
  const products = new Map();
  for (const point of points || []) {
    if (!point?.product_key || !point?.user_pseudonym
      || !Number.isFinite(point.normalized_price_cents)
      || point.normalized_price_cents < 0) continue;
    if (!products.has(point.product_key)) products.set(point.product_key, new Map());
    const users = products.get(point.product_key);
    if (!users.has(point.user_pseudonym)) users.set(point.user_pseudonym, []);
    users.get(point.user_pseudonym).push(point);
  }
  const groups = [];
  for (const [productKey, users] of products) {
    const summaries = [...users].map(([user, userPoints]) => ({
      user,
      points: userPoints,
      median: median(userPoints.map(point => point.normalized_price_cents)),
    }));
    if (summaries.length < 2) continue;
    const low = summaries.slice().sort((a, b) => a.median - b.median
      || b.points.length - a.points.length || a.user.localeCompare(b.user))[0];
    const high = summaries.filter(item => item.user !== low.user).sort((a, b) => b.median - a.median
      || b.points.length - a.points.length || a.user.localeCompare(b.user))[0];
    const byTime = (a, b) => Date.parse(a.fetch_ts) - Date.parse(b.fetch_ts)
      || String(a.observation_id).localeCompare(String(b.observation_id));
    const pointsA = low.points.slice().sort(byTime);
    const pointsB = high.points.slice().sort(byTime);
    groups.push({
      productKey,
      productName: pointsA[0]?.product_name || pointsB[0]?.product_name || productKey,
      userA: low.user,
      userB: high.user,
      pointsA,
      pointsB,
      points: [...pointsA, ...pointsB],
    });
  }
  return groups.sort((a, b) => String(a.productKey).localeCompare(String(b.productKey)));
}

export function buildComparisonPairs(pointsA, pointsB, limit = 1000) {
  const a = validPoints(pointsA);
  const b = validPoints(pointsB);
  const drawLimit = Number.isFinite(limit) ? Math.max(0, Math.floor(limit)) : 1000;
  const pairs = [];
  let candidateCount = 0;
  for (const pointA of a) {
    for (const pointB of b) {
      if (pointA.user_pseudonym === pointB.user_pseudonym) continue;
      candidateCount += 1;
      if (pairs.length < drawLimit) pairs.push({a: pointA, b: pointB});
    }
  }
  return {pairs, candidateCount, truncated: pairs.length < candidateCount};
}
