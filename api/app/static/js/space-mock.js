export function createMockData() {
  const users = ['u_demo_a', 'u_demo_b', 'u_demo_c', 'u_demo_d'];
  const products = [
    ['p_demo_phone', 'PHONE-DEMO', '演示智能手机', '手机数码', '手机', 'jd', 10000],
    ['p_demo_laptop', 'LAPTOP-DEMO', '演示笔记本电脑', '电脑办公', '笔记本电脑', 'jd', 50000],
    ['p_demo_headset', 'HEADSET-DEMO', '演示降噪耳机', '手机数码', '耳机音箱', 'amazon', 1200],
  ];
  const points = [];
  products.forEach((product, productIndex) => {
    const [productKey, productId, productName, categoryL1, categoryL2, platform, base] = product;
    users.forEach((user, userIndex) => {
      for (let sample = 0; sample < 4; sample += 1) {
        const multiplier = 1 + userIndex * 0.07 + sample * 0.004;
        const price = Math.round(base * multiplier);
        const currency = platform === 'amazon' ? 'USD' : 'CNY';
        points.push({
          observation_id: `demo-${productIndex}-${userIndex}-${sample}`,
          fetch_ts: new Date(Date.UTC(2026, 9, 20 + sample, 8 + userIndex)).toISOString(),
          user_pseudonym: user,
          platform_code: platform,
          product_id: productId,
          product_key: productKey,
          seller_id: 'demo-seller',
          product_name: productName,
          category_l1: categoryL1,
          category_l2: categoryL2,
          category_confidence: 1,
          basis_price_cents: price,
          display_price_cents: price,
          actual_pay_price_cents: price,
          price_basis: 'DISPLAY',
          currency,
          normalized_price_cents: platform === 'amazon' ? Math.round(price * 7.2) : price,
          exchange_rate: platform === 'amazon' ? 7.2 : 1,
          exchange_rate_date: platform === 'amazon' ? '2026-10-29' : null,
          exchange_stale: false,
          promo_type: userIndex % 2 ? 'coupon' : 'none',
          promo_label: userIndex % 2 ? '演示优惠券' : '',
          discount_coupon_amount_cents: userIndex % 2 ? 100 : null,
          is_login: true,
          membership_level: userIndex % 2 ? 'plus' : 'basic',
          is_new_user: userIndex === 0,
          register_days: 30 + userIndex * 100,
          ip_city: ['上海', '北京', '深圳', '杭州'][userIndex],
          shipping_city: ['上海', '北京', '深圳', '杭州'][userIndex],
          device_price_score_estimate: 50 + userIndex * 10,
          stock_hint: '现货',
          peak_hour: false,
          sample_size: 16,
          price_gap_suspected: userIndex > 0,
          price_gap_direction: userIndex > 0 ? 'HIGH' : 'LOW',
          statistical_status: 'DESCRIPTIVE_SMALL_SAMPLE',
        });
      }
    });
  });
  const byProduct = new Map();
  points.forEach(point => {
    if (!byProduct.has(point.product_key)) byProduct.set(point.product_key, []);
    byProduct.get(point.product_key).push(point);
  });
  byProduct.forEach(group => {
    const prices = group.map(point => point.normalized_price_cents).sort((a, b) => a - b);
    const middle = (prices[7] + prices[8]) / 2;
    group.forEach(point => { point.price_deviation = (point.normalized_price_cents - middle) / middle; });
  });
  const edges = [];
  points.forEach((point, index) => {
    for (let other = index + 1; other < points.length; other += 1) {
      const target = points[other];
      if (point.product_key !== target.product_key) continue;
      if (edges.length < 900 && point.user_pseudonym !== target.user_pseudonym && point.price_gap_direction !== target.price_gap_direction) {
        edges.push({type: 'PRICE_GAP', source: point.observation_id, target: target.observation_id, product_key: point.product_key, diff_percent: 7});
      }
      if (edges.length < 900 && point.user_pseudonym === target.user_pseudonym) {
        edges.push({type: 'SAME_USER_PRODUCT', source: point.observation_id, target: target.observation_id, product_key: point.product_key});
      }
    }
  });
  const statistics = products.map(product => ({
    platform_code: product[5], product_key: product[0], user_a: users[0], user_b: users[1],
    n_a: 4, n_b: 4, median_a: product[6], median_b: Math.round(product[6] * 1.07),
    diff_percent: 6.54, suspected: true, status: 'DESCRIPTIVE_SMALL_SAMPLE',
    mann_whitney_u: null, mann_whitney_p: null, welch_t: null, welch_p: null,
  }));
  return {
    points, edges, statistics,
    platform_replication: {jd: {product_count: 2, suspected: true}, amazon: {product_count: 1, suspected: false}},
    meta: {
      total: points.length, returned: points.length, truncated: false,
      normalized_total: points.length, uncached_products: 0, classification_status: 'idle',
      edge_candidate_count: edges.length, edge_limit: 1000, edges_truncated: false,
      exchange_rate: {base: 'USD', quote: 'CNY', rate: 7.2, rate_date: '2026-10-29'}, warnings: [],
    },
  };
}
