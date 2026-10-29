import * as THREE from 'three';
import { OrbitControls } from '/static/vendor/OrbitControls.js';
import { businessCoordinates, featureProjection, filterPoints, toCSV } from './space-core.js';
import { createMockData } from './space-mock.js';

const $ = id => document.getElementById(id);
const emptyData = () => ({points: [], edges: [], statistics: [], platform_replication: {}, meta: {warnings: []}});
const state = {
  data: emptyData(), filtered: [], selectedProduct: null, selectedPoint: null,
  view: window.innerWidth < 700 ? '2d' : '3d', mock: false, playing: false,
  playTimer: null, classificationTimer: null, visibleEdges: 0,
};
const relationColors = {
  SAME_PRODUCT: 0x63a4ff, SAME_USER: 0x9d8cff, SAME_USER_PRODUCT: 0x46d9d0,
  TIME_NEIGHBOR: 0x8093a8, PRICE_GAP: 0xff7185, PROMO_DIFFERENCE: 0xf6bd60,
};
const palette = ['#63a4ff','#ff7185','#46d9d0','#f6bd60','#9d8cff','#69db7c','#ef8fca','#70c7e8','#d7a66f','#a6d96a','#b0a199','#7fd4b5','#e68a68','#8fa8e8','#a8b3c2'];
const statusNames = {idle: '分类空闲', running: '后台分类中', success: '分类已更新', error: '后台分类失败', not_configured: '分类服务未配置'};

function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
}
function hash(text) {
  let value = 0;
  for (const char of String(text || 'unknown')) value = (Math.imul(value, 31) + char.codePointAt(0)) >>> 0;
  return value;
}
function formatPrice(value, currency = 'CNY') {
  return Number.isFinite(value) ? `${(value / 100).toFixed(2)} ${currency}` : '—';
}
function formatTime(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '—' : date.toISOString().replace('T', ' ').replace('.000Z', 'Z');
}
function inputUTC(value) {
  if (!value) return '';
  return value.endsWith('Z') ? value : `${value}${value.length === 16 ? ':00' : ''}Z`;
}
function setStatus(text) { $('classificationStatus').textContent = text; }

// One THREE.Points draw call and one THREE.LineSegments per enabled relation type.
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(48, 1, 0.1, 2000);
const renderer = new THREE.WebGLRenderer({antialias: true, alpha: true});
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
renderer.setClearColor(0x07111f, 0);
$('scene').appendChild(renderer.domElement);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.08;
controls.screenSpacePanning = true;
controls.minDistance = 20;
controls.maxDistance = 600;
const grid = new THREE.GridHelper(120, 12, 0x28425f, 0x172b42);
grid.rotation.x = Math.PI / 2;
grid.position.z = -12;
scene.add(grid);
scene.add(new THREE.AxesHelper(18));
const relationGroup = new THREE.Group();
scene.add(relationGroup);
let pointCloud = null;
const raycaster = new THREE.Raycaster();
raycaster.params.Points.threshold = 1.8;
const pointer = new THREE.Vector2();
let pointerDown = null;

function resize() {
  const width = Math.max(1, $('scene').clientWidth);
  const height = Math.max(1, $('scene').clientHeight);
  renderer.setSize(width, height, false);
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
}
window.addEventListener('resize', resize);
resize();

function animate() {
  requestAnimationFrame(animate);
  controls.update();
  renderer.render(scene, camera);
}
animate();

function setCamera() {
  if (state.view === '2d') {
    camera.position.set(0, 0, 135);
    camera.up.set(0, 1, 0);
    controls.enableRotate = false;
  } else {
    camera.position.set(75, 65, 115);
    camera.up.set(0, 1, 0);
    controls.enableRotate = true;
  }
  controls.target.set(0, 0, 0);
  controls.update();
}
setCamera();

function colorFor(point) {
  const dimension = $('colorDimension').value;
  if (dimension === 'gap') {
    if (point.price_gap_direction === 'HIGH') return '#ff7185';
    if (point.price_gap_direction === 'LOW') return '#46d9d0';
    return '#8093a8';
  }
  const key = dimension === 'category' ? (point.category_l1 || '未分类／待分类')
    : dimension === 'user' ? point.user_pseudonym : point.platform_code;
  return palette[hash(key) % palette.length];
}

function disposeObject(object) {
  if (!object) return;
  object.geometry?.dispose();
  if (Array.isArray(object.material)) object.material.forEach(material => material.dispose());
  else object.material?.dispose();
}

function renderRelations(positionById) {
  while (relationGroup.children.length) {
    const child = relationGroup.children[0];
    relationGroup.remove(child);
    disposeObject(child);
  }
  const enabled = new Set([...document.querySelectorAll('[data-relation]:checked')].map(input => input.dataset.relation));
  const byType = new Map();
  state.data.edges.forEach(edge => {
    if (!enabled.has(edge.type) || !positionById.has(edge.source) || !positionById.has(edge.target)) return;
    if (!byType.has(edge.type)) byType.set(edge.type, []);
    byType.get(edge.type).push(edge);
  });
  state.visibleEdges = 0;
  byType.forEach((edges, type) => {
    const positions = [];
    edges.forEach(edge => {
      positions.push(...positionById.get(edge.source), ...positionById.get(edge.target));
    });
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
    const material = new THREE.LineBasicMaterial({color: relationColors[type] || 0x8093a8, transparent: true, opacity: type === 'PRICE_GAP' ? 0.72 : 0.24});
    relationGroup.add(new THREE.LineSegments(geometry, material));
    state.visibleEdges += edges.length;
  });
  $('edgeMeta').textContent = `${state.visibleEdges} 条可见关系 / ${state.data.edges.length} 条已返回`;
}

function renderScene() {
  if (pointCloud) {
    scene.remove(pointCloud);
    disposeObject(pointCloud);
    pointCloud = null;
  }
  const points = state.filtered;
  $('emptyState').hidden = points.length > 0;
  if (!points.length) {
    renderRelations(new Map());
    return;
  }
  const mode = $('coordinateMode').value;
  const coordinates = mode === 'feature'
    ? points.map(point => ({id: point.observation_id, position: featureProjection(point)}))
    : businessCoordinates(points);
  const positionById = new Map();
  const positions = new Float32Array(points.length * 3);
  const colors = new Float32Array(points.length * 3);
  const sizes = new Float32Array(points.length);
  const alphas = new Float32Array(points.length);
  const borders = new Float32Array(points.length);
  points.forEach((point, index) => {
    const coordinate = coordinates[index].position;
    const position = [coordinate[0], coordinate[1], state.view === '2d' ? 0 : coordinate[2]];
    positionById.set(point.observation_id, position);
    positions.set(position, index * 3);
    const color = new THREE.Color(colorFor(point));
    colors.set([color.r, color.g, color.b], index * 3);
    const selected = !state.selectedProduct || state.selectedProduct === point.product_key;
    sizes[index] = state.selectedPoint?.observation_id === point.observation_id ? 15 : selected ? 9 : 5;
    alphas[index] = selected ? 0.92 : 0.10;
    borders[index] = Number.isFinite(point.normalized_price_cents) ? 0 : 1;
  });
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
  geometry.setAttribute('size', new THREE.BufferAttribute(sizes, 1));
  geometry.setAttribute('alpha', new THREE.BufferAttribute(alphas, 1));
  geometry.setAttribute('border', new THREE.BufferAttribute(borders, 1));
  const material = new THREE.ShaderMaterial({
    transparent: true,
    depthWrite: false,
    vertexShader: `
      attribute vec3 color;
      attribute float size;
      attribute float alpha;
      attribute float border;
      varying vec3 vColor;
      varying float vAlpha;
      varying float vBorder;
      void main() {
        vColor = color; vAlpha = alpha; vBorder = border;
        vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
        gl_PointSize = clamp(size * (180.0 / max(20.0, -mvPosition.z)), 3.0, 28.0);
        gl_Position = projectionMatrix * mvPosition;
      }`,
    fragmentShader: `
      varying vec3 vColor;
      varying float vAlpha;
      varying float vBorder;
      void main() {
        float distanceToCenter = distance(gl_PointCoord, vec2(0.5));
        if (distanceToCenter > 0.5) discard;
        float edge = smoothstep(0.32, 0.5, distanceToCenter);
        vec3 borderColor = vBorder > 0.5 ? vec3(0.96, 0.55, 0.20) : vec3(1.0);
        vec3 finalColor = mix(vColor, borderColor, edge * (vBorder > 0.5 ? 0.95 : 0.45));
        gl_FragColor = vec4(finalColor, vAlpha);
      }`,
  });
  pointCloud = new THREE.Points(geometry, material);
  scene.add(pointCloud);
  renderRelations(positionById);
}

function currentFilters() {
  const max = Number($('playPosition').max);
  const position = Number($('playPosition').value);
  const timeline = [...state.data.points].sort((a, b) => Date.parse(a.fetch_ts) - Date.parse(b.fetch_ts));
  return {
    platform: $('platformFilter').value,
    category: $('categoryFilter').value,
    user: $('userFilter').value,
    city: $('cityFilter').value,
    promo: $('promoFilter').value,
    gap: $('gapFilter').value,
    search: $('searchInput').value,
    start: inputUTC($('startTime').value),
    end: inputUTC($('endTime').value),
    playhead: timeline.length && position < max ? timeline[position]?.fetch_ts : null,
  };
}

function applyFilters() {
  state.filtered = filterPoints(state.data.points, currentFilters());
  $('visibleCount').textContent = `${state.filtered.length} 个可见点`;
  $('axisNote').textContent = $('coordinateMode').value === 'feature'
    ? '确定性特征哈希投影（非 PCA / t-SNE / UMAP）'
    : state.view === '2d' ? 'X：时间　Y：分类（2D 压平价格偏差）' : 'X：时间　Y：分类　Z：相对中位价偏差';
  renderScene();
  renderTable();
  renderStatistics();
  renderComparison();
}

function renderTable() {
  $('pointRows').innerHTML = state.filtered.slice(0, 500).map(point => `<tr data-id="${esc(point.observation_id)}">
    <td>${esc(formatTime(point.fetch_ts))}</td>
    <td><strong>${esc(point.product_name)}</strong><br><span class="muted">${esc(point.category_l1 || '未分类／待分类')} / ${esc(point.category_l2 || '待分类')}</span></td>
    <td>${esc(point.platform_code)}</td><td>${esc(point.user_pseudonym || '—')}</td>
    <td>${esc(formatPrice(point.basis_price_cents, point.currency))}</td>
    <td>${esc(formatPrice(point.normalized_price_cents))}</td>
    <td>${esc(point.promo_label || point.promo_type || '—')}</td>
    <td>${esc(point.ip_city || point.shipping_city || '—')}</td>
    <td class="${point.price_gap_direction === 'HIGH' ? 'high' : point.price_gap_direction === 'LOW' ? 'low' : ''}">${esc(point.price_gap_direction || '—')}<br><small>${esc(point.statistical_status || '')}</small></td>
  </tr>`).join('');
  $('pointRows').querySelectorAll('tr').forEach(row => row.addEventListener('click', () => selectPoint(row.dataset.id)));
}

function pointDetails(point) {
  return `<h3>${esc(point.product_name)}</h3><dl>
    <dt>观测 ID</dt><dd>${esc(point.observation_id)}</dd><dt>UTC 时间</dt><dd>${esc(formatTime(point.fetch_ts))}</dd>
    <dt>用户假名</dt><dd>${esc(point.user_pseudonym || '—')}</dd><dt>平台 / 卖家</dt><dd>${esc(point.platform_code)} / ${esc(point.seller_id || '—')}</dd>
    <dt>分类</dt><dd>${esc(point.category_l1 || '未分类／待分类')} / ${esc(point.category_l2 || '待分类')}</dd>
    <dt>原始价格</dt><dd>${esc(formatPrice(point.basis_price_cents, point.currency))}（${esc(point.price_basis)}）</dd>
    <dt>折算价</dt><dd>${esc(formatPrice(point.normalized_price_cents))}</dd>
    <dt>中位价偏差</dt><dd>${Number.isFinite(point.price_deviation) ? esc((point.price_deviation * 100).toFixed(2) + '%') : '—'}</dd>
    <dt>促销 / 券</dt><dd>${esc(point.promo_label || point.promo_type || '—')} / ${esc(formatPrice(point.discount_coupon_amount_cents, point.currency))}</dd>
    <dt>会员 / 新用户</dt><dd>${esc(point.membership_level || '—')} / ${point.is_new_user === null || point.is_new_user === undefined ? '未知' : point.is_new_user ? '是' : '否'}</dd>
    <dt>城市</dt><dd>${esc(point.ip_city || '—')} / ${esc(point.shipping_city || '—')}</dd>
    <dt>价差方向</dt><dd>${esc(point.price_gap_direction || '—')}；${esc(point.statistical_status || '—')}</dd>
    <dt>样本量</dt><dd>${esc(point.sample_size ?? '—')}</dd><dt>版本</dt><dd>${esc(point.source_code_version || '—')}</dd>
  </dl>`;
}

function renderDetail() {
  $('pointDetail').innerHTML = state.selectedPoint ? pointDetails(state.selectedPoint) : '点击点或表格记录查看详情；再次点击空白处取消选择。';
}

function selectPoint(id) {
  const point = state.data.points.find(item => item.observation_id === id);
  if (!point) return;
  state.selectedPoint = point;
  state.selectedProduct = point.product_key;
  renderDetail();
  applyFilters();
}

function renderStatistics() {
  const visibleProducts = new Set(state.filtered.map(point => point.product_key));
  const stats = state.data.statistics.filter(stat => visibleProducts.has(stat.product_key) && (!state.selectedProduct || stat.product_key === state.selectedProduct));
  const platform = Object.entries(state.data.platform_replication).map(([code, item]) => `<div class="stat-card"><strong>${esc(code)}</strong>：${item.suspected ? '跨商品疑似复现' : '未达到平台级复现'}<br><small>${item.product_count} 个疑似商品；平台级至少需 2 个</small></div>`).join('');
  const rows = stats.slice(0, 50).map(stat => `<div class="stat-card"><strong>${esc(stat.user_a)} ↔ ${esc(stat.user_b)}</strong>　${esc(stat.diff_percent.toFixed(2))}%<br><small>n=${stat.n_a}/${stat.n_b}；中位价 ${esc(formatPrice(stat.median_a))} / ${esc(formatPrice(stat.median_b))}<br>${stat.status === 'TESTS_AVAILABLE' ? `MWU p=${esc(stat.mann_whitney_p)}；Welch p=${esc(stat.welch_p)}` : '任一组 n<3，仅描述性统计'}；${stat.suspected ? '疑似价差' : '未达 5% 阈值'}</small></div>`).join('');
  $('statisticsList').innerHTML = platform + rows || '暂无跨用户可比样本。';
}

function comparisonSeries(user, productKey) {
  return state.data.points.filter(point => point.product_key === productKey && point.user_pseudonym === user).sort((a, b) => Date.parse(a.fetch_ts) - Date.parse(b.fetch_ts));
}

function renderComparison() {
  const userA = $('compareUserA').value;
  const userB = $('compareUserB').value;
  const productKey = state.selectedProduct || (new Set(state.filtered.map(point => point.product_key)).size === 1 ? state.filtered[0]?.product_key : null);
  if (!userA || !userB || userA === userB || !productKey) {
    $('comparison').textContent = '选择两个不同用户，并点击一个商品点或筛选到单一商品。';
    return;
  }
  const a = comparisonSeries(userA, productKey);
  const b = comparisonSeries(userB, productKey);
  if (!a.length || !b.length) {
    $('comparison').textContent = '当前商品下至少一组没有观测序列。';
    return;
  }
  const all = [...a, ...b];
  const min = Math.min(...all.map(point => point.normalized_price_cents ?? point.basis_price_cents));
  const max = Math.max(...all.map(point => point.normalized_price_cents ?? point.basis_price_cents));
  const polyline = series => series.map((point, index) => {
    const value = point.normalized_price_cents ?? point.basis_price_cents;
    const x = series.length === 1 ? 150 : 10 + index / (series.length - 1) * 280;
    const y = max === min ? 60 : 105 - (value - min) / (max - min) * 90;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');
  $('comparison').innerHTML = `<svg viewBox="0 0 300 125" width="100%" height="125" role="img" aria-label="双用户价格序列"><line x1="10" y1="105" x2="290" y2="105" stroke="#34506e"/><polyline points="${polyline(a)}" fill="none" stroke="#46d9d0" stroke-width="2"/><polyline points="${polyline(b)}" fill="none" stroke="#ff7185" stroke-width="2"/></svg><div><span class="low">● ${esc(userA)}</span> ${a.length} 点　<span class="high">● ${esc(userB)}</span> ${b.length} 点</div><div>同一商品、各自 UTC 时间序列；纵轴使用可比折算价，缺失时仅作原币展示。</div>`;
}

function populateControls() {
  const points = state.data.points;
  const fill = (id, values, allLabel) => {
    const select = $(id);
    const previous = select.value;
    select.innerHTML = `<option value="">${allLabel}</option>` + [...new Set(values.filter(Boolean))].sort().map(value => `<option value="${esc(value)}">${esc(value)}</option>`).join('');
    select.value = previous;
  };
  fill('platformFilter', points.map(point => point.platform_code), '全部平台');
  fill('categoryFilter', points.map(point => point.category_l1 || ''), '全部分类');
  fill('compareUserA', points.map(point => point.user_pseudonym), '请选择');
  fill('compareUserB', points.map(point => point.user_pseudonym), '请选择');
  const timeline = [...points].sort((a, b) => Date.parse(a.fetch_ts) - Date.parse(b.fetch_ts));
  $('playPosition').max = Math.max(0, timeline.length - 1);
  $('playPosition').value = $('playPosition').max;
  $('playLabel').textContent = timeline.length ? `截至 ${formatTime(timeline.at(-1).fetch_ts)}` : '全部时间';
}

function renderMeta() {
  const meta = state.data.meta || {};
  $('dataMode').textContent = state.mock ? '演示数据' : '真实数据';
  $('dataMode').classList.toggle('mock', state.mock);
  $('pointMeta').textContent = `${state.data.points.length} 个观测点，${meta.normalized_total || 0} 个可比价`;
  $('samplingMeta').textContent = meta.truncated ? `仅最新 ${meta.returned} / ${meta.total} 条，已截断` : `数据库共 ${meta.total ?? state.data.points.length} 条`;
  $('rateMeta').textContent = meta.exchange_rate?.rate ? `USD/CNY ${meta.exchange_rate.rate}（${meta.exchange_rate.rate_date}）` : '';
  const warnings = [...(meta.warnings || [])];
  if (meta.edges_truncated) warnings.push(`关系候选 ${meta.edge_candidate_count} 条，仅返回前 ${meta.edge_limit} 条`);
  if (meta.uncached_products) warnings.push(`${meta.uncached_products} 个商品待后台分类，当前显示“未分类／待分类”`);
  $('warnings').textContent = warnings.join('；');
  setStatus(statusNames[meta.classification_status] || meta.classification_status || '尚未加载');
}

function setData(data, mock = false) {
  stopPlay();
  state.data = data;
  state.mock = mock;
  state.selectedPoint = null;
  state.selectedProduct = null;
  renderDetail();
  populateControls();
  renderMeta();
  applyFilters();
}

async function loadData() {
  if (state.classificationTimer) clearTimeout(state.classificationTimer);
  const key = localStorage.getItem(window.SPACE_STORAGE_KEY) || '';
  if (!key) {
    setData(emptyData());
    setStatus('请先在管理控制台登录');
    return;
  }
  setStatus('正在读取观测数据…');
  try {
    const response = await fetch('/api/space/points', {headers: {'X-API-Key': key}});
    if (!response.ok) throw new Error(response.status === 401 ? '管理员会话已失效，请返回控制台重新登录' : `读取失败（${response.status}）`);
    const data = await response.json();
    setData(data, false);
    if (data.meta.classification_status === 'running') pollClassification();
  } catch (error) {
    setData(emptyData());
    setStatus(error.message);
  }
}

async function pollClassification() {
  const key = localStorage.getItem(window.SPACE_STORAGE_KEY) || '';
  try {
    const response = await fetch('/api/space/classification-status', {headers: {'X-API-Key': key}});
    if (!response.ok) return;
    const status = await response.json();
    setStatus(`${statusNames[status.status] || status.status} ${status.processed}/${status.total}`);
    if (status.status === 'running') {
      state.classificationTimer = setTimeout(pollClassification, 4000);
    } else if (status.status === 'success') {
      state.classificationTimer = setTimeout(loadData, 800);
    }
  } catch (_) {
    state.classificationTimer = setTimeout(pollClassification, 8000);
  }
}

function stopPlay() {
  state.playing = false;
  if (state.playTimer) clearInterval(state.playTimer);
  state.playTimer = null;
  $('playButton').textContent = '播放';
}
function play() {
  if (state.playing) { stopPlay(); return; }
  if (!state.data.points.length) return;
  state.playing = true;
  $('playButton').textContent = '停止';
  const max = Number($('playPosition').max);
  if (Number($('playPosition').value) >= max) $('playPosition').value = 0;
  state.playTimer = setInterval(() => {
    const next = Number($('playPosition').value) + 1;
    if (next > Number($('playPosition').max)) { stopPlay(); return; }
    $('playPosition').value = next;
    updatePlayLabel();
    applyFilters();
  }, 300);
  updatePlayLabel();
  applyFilters();
}
function updatePlayLabel() {
  const timeline = [...state.data.points].sort((a, b) => Date.parse(a.fetch_ts) - Date.parse(b.fetch_ts));
  const point = timeline[Number($('playPosition').value)];
  $('playLabel').textContent = point ? `截至 ${formatTime(point.fetch_ts)}` : '全部时间';
}

function switchView(view) {
  state.view = view;
  document.querySelectorAll('[data-view]').forEach(button => button.classList.toggle('active', button.dataset.view === view));
  $('visualPanel').classList.toggle('hidden', view === 'table');
  $('tablePanel').classList.toggle('hidden', view === 'table' ? false : true);
  if (view !== 'table') { setCamera(); resize(); }
  applyFilters();
}

function pointerCoordinates(event) {
  const rect = renderer.domElement.getBoundingClientRect();
  pointer.x = (event.clientX - rect.left) / rect.width * 2 - 1;
  pointer.y = -(event.clientY - rect.top) / rect.height * 2 + 1;
}
renderer.domElement.addEventListener('pointerdown', event => { pointerDown = [event.clientX, event.clientY]; });
renderer.domElement.addEventListener('pointermove', event => {
  if (!pointCloud) return;
  pointerCoordinates(event);
  raycaster.setFromCamera(pointer, camera);
  const hit = raycaster.intersectObject(pointCloud)[0];
  const tooltip = $('tooltip');
  if (!hit) { tooltip.classList.remove('show'); renderer.domElement.style.cursor = 'grab'; return; }
  const point = state.filtered[hit.index];
  tooltip.innerHTML = pointDetails(point);
  tooltip.style.left = `${Math.min(window.innerWidth - 375, event.clientX + 14)}px`;
  tooltip.style.top = `${Math.min(window.innerHeight - 300, event.clientY + 14)}px`;
  tooltip.classList.add('show');
  renderer.domElement.style.cursor = 'pointer';
});
renderer.domElement.addEventListener('pointerleave', () => $('tooltip').classList.remove('show'));
renderer.domElement.addEventListener('pointerup', event => {
  if (!pointerDown || Math.hypot(event.clientX - pointerDown[0], event.clientY - pointerDown[1]) > 5) return;
  pointerCoordinates(event);
  raycaster.setFromCamera(pointer, camera);
  const hit = pointCloud ? raycaster.intersectObject(pointCloud)[0] : null;
  if (hit) selectPoint(state.filtered[hit.index].observation_id);
  else { state.selectedPoint = null; state.selectedProduct = null; renderDetail(); applyFilters(); }
});

['platformFilter','categoryFilter','userFilter','cityFilter','promoFilter','gapFilter','searchInput','coordinateMode','colorDimension'].forEach(id => {
  $(id).addEventListener(id === 'searchInput' || id === 'userFilter' || id === 'cityFilter' ? 'input' : 'change', applyFilters);
});
$('coordinateMode').addEventListener('change', () => { setCamera(); applyFilters(); });
$('colorDimension').addEventListener('change', applyFilters);
['startTime','endTime'].forEach(id => $(id).addEventListener('change', applyFilters));
document.querySelectorAll('[data-relation]').forEach(input => input.addEventListener('change', applyFilters));
document.querySelectorAll('[data-view]').forEach(button => button.addEventListener('click', () => switchView(button.dataset.view)));
['compareUserA','compareUserB'].forEach(id => $(id).addEventListener('change', renderComparison));
$('playPosition').addEventListener('input', () => { updatePlayLabel(); applyFilters(); });
$('playButton').addEventListener('click', play);
$('refreshButton').addEventListener('click', loadData);
$('mockButton').addEventListener('click', () => {
  if (!state.mock && state.data.points.length) { setStatus('已有真实数据；演示模式仅在没有真实点时开放'); return; }
  setData(createMockData(), true);
  setStatus('当前全部为演示数据，不会写入数据库');
});
$('exportButton').addEventListener('click', () => {
  const blob = new Blob([toCSV(state.filtered)], {type: 'text/csv;charset=utf-8'});
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `${state.mock ? 'demo-' : ''}observation-space-${new Date().toISOString().slice(0, 10)}.csv`;
  link.click();
  URL.revokeObjectURL(url);
});

switchView(state.view);
loadData();
