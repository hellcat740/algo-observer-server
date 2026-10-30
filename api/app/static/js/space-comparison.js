function validPoints(points) {
  return (points || []).filter(point => (
    point && Number.isFinite(point.normalized_price_cents) && point.normalized_price_cents >= 0
  )).slice().sort((a, b) => String(a.observation_id).localeCompare(String(b.observation_id)));
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
