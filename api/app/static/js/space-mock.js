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
          statistical_status: 'TESTS_AVAILABLE',
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
    diff_percent: 6.54, suspected: true, status: 'TESTS_AVAILABLE',
    mann_whitney_u: 0, mann_whitney_p: 0.02, welch_t: -8.2, welch_p: 0.001,
  }));
  return {
    points, edges, statistics,
    category_taxonomy: {
      '手机数码': ['手机', '手机配件', '平板电脑', '智能手表', '耳机音箱', '摄影摄像', '游戏机', '智能家居', '其他数码'],
      '电脑办公': ['笔记本电脑', '台式电脑', '显示器', '键鼠外设', '打印机', '存储设备', '办公软件', '其他办公用品'],
      '家用电器': ['电视', '冰箱', '洗衣机', '空调', '厨房电器', '生活电器', '影音设备', '其他家电'],
      '服饰鞋包': ['女装', '男装', '童装', '鞋靴', '箱包', '内衣配饰', '珠宝饰品', '其他服饰'],
      '美妆个护': ['面部护肤', '彩妆', '香水', '洗发护发', '身体护理', '口腔护理', '美容仪器', '其他个护'],
      '母婴玩具': ['奶粉辅食', '尿裤湿巾', '婴儿洗护', '婴儿车床', '玩具模型', '积木拼装', '其他母婴玩具'],
      '食品生鲜': ['休闲食品', '粮油调味', '饮料酒水', '水果生鲜', '乳制品', '保健食品', '方便食品', '其他食品'],
      '家居家装': ['家具', '床上用品', '厨房用品', '卫浴用品', '灯具照明', '五金工具', '装饰摆件', '其他家居'],
      '图书文娱': ['图书', '电子书', '音像制品', '文创用品', '乐器', '艺术用品', '其他文娱'],
      '运动户外': ['健身器材', '运动鞋服', '球类运动', '骑行装备', '露营装备', '钓鱼用品', '其他运动户外'],
      '汽车用品': ['行车记录仪', '轮胎轮毂', '汽车内饰', '车载电器', '保养用品', '汽车配件', '其他汽车用品'],
      '医疗健康': ['家用医疗器械', '医用耗材', '滋补保健', '康复护理', '隐形眼镜', '其他医疗健康'],
      '宠物用品': ['宠物主粮', '宠物零食', '宠物玩具', '宠物窝垫', '宠物清洁', '宠物医疗', '其他宠物用品'],
      '虚拟服务': ['软件会员', '网盘服务', '充值服务', '云服务', '在线课程', '其他虚拟服务'],
      '其他／无法判断': ['其他', '无法判断'],
    },
    platform_replication: {jd: {product_count: 2, suspected: true}, amazon: {product_count: 1, suspected: false}},
    meta: {
      total: points.length, returned: points.length, truncated: false,
      normalized_total: points.length, uncached_products: 0, classification_status: 'idle',
      edge_candidate_count: edges.length, edge_limit: 1000, edges_truncated: false,
      exchange_rate: {base: 'USD', quote: 'CNY', rate: 7.2, rate_date: '2026-10-29'}, warnings: [],
    },
  };
}
