import * as THREE from 'three';
import { OrbitControls } from '/static/vendor/OrbitControls.js';
import { filterPoints, toCSV } from './space-core.js';
import { buildSemanticLayout, userColor } from './space-layout.js';
import { movementVector } from './space-navigation.js';
import { buildComparisonGeometry, categoryOpacity } from './space-volumes.js';
import { buildAnalyzableComparisonGroups } from './space-comparison.js';
import { comparePriceGroups } from './comparison-rule.js';
import { createMockData } from './space-mock.js';

const $ = id => document.getElementById(id);
const emptyData = () => ({points: [], edges: [], statistics: [], category_taxonomy: {}, platform_replication: {}, meta: {warnings: []}});
const state = {
  data: emptyData(), filtered: [], layout: buildSemanticLayout([], {}),
  selectedProduct: null, selectedPoint: null,
  view: window.innerWidth < 700 ? '2d' : '3d', mock: false, playing: false,
  playTimer: null, classificationTimer: null,
};
const statusNames = {idle: '分类空闲', running: '后台分类中', success: '分类已更新', error: '后台分类失败', not_configured: '分类服务未配置'};
const pressedKeys = new Set();

function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
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

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(48, 1, 0.1, 2400);
camera.up.set(0, 0, 1);
const renderer = new THREE.WebGLRenderer({antialias: true, alpha: true});
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
renderer.setClearColor(0x211811, 0);
$('scene').appendChild(renderer.domElement);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.08;
controls.screenSpacePanning = true;
controls.minDistance = 20;
controls.maxDistance = 900;

function createGridPlane(rotation) {
  const geometry = new THREE.PlaneGeometry(2000, 2000);
  const material = new THREE.ShaderMaterial({
    transparent: true,
    depthWrite: false,
    side: THREE.DoubleSide,
    uniforms: {
      uStep: {value: 10},
      uColor: {value: new THREE.Color(0x6f5a43)},
    },
    vertexShader: `
      varying vec2 vUv;
      void main() {
        vUv = uv;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }`,
    fragmentShader: `
      varying vec2 vUv;
      uniform float uStep;
      uniform vec3 uColor;
      void main() {
        vec2 coord = (vUv - 0.5) * 2000.0 / uStep;
        vec2 width = fwidth(coord);
        vec2 grid = abs(fract(coord - 0.5) - 0.5) / max(width, vec2(0.0001));
        float line = 1.0 - min(min(grid.x, grid.y), 1.0);
        float fade = 1.0 - smoothstep(0.18, 0.5, distance(vUv, vec2(0.5)));
        float alpha = line * fade * 0.16;
        if (alpha < 0.002) discard;
        gl_FragColor = vec4(uColor, alpha);
      }`,
  });
  const plane = new THREE.Mesh(geometry, material);
  plane.rotation.set(...rotation);
  plane.renderOrder = -10;
  scene.add(plane);
  return plane;
}
const gridPlanes = [
  createGridPlane([0, 0, 0]),
  createGridPlane([Math.PI / 2, 0, 0]),
  createGridPlane([0, Math.PI / 2, 0]),
];

const categoryGroup = new THREE.Group();
categoryGroup.renderOrder = 0;
scene.add(categoryGroup);
const comparisonGroup = new THREE.Group();
comparisonGroup.renderOrder = 3;
scene.add(comparisonGroup);
let pointCloud = null;
const raycaster = new THREE.Raycaster();
raycaster.params.Points.threshold = 1.8;
const pointer = new THREE.Vector2();
let pointerDown = null;
const clock = new THREE.Clock();

function resize() {
  const width = Math.max(1, $('scene').clientWidth);
  const height = Math.max(1, $('scene').clientHeight);
  renderer.setSize(width, height, false);
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
}
window.addEventListener('resize', resize);
resize();

function updateMovement(delta) {
  if (!['2d', '3d'].includes(state.view) || !pressedKeys.size) return;
  const forward = new THREE.Vector3();
  camera.getWorldDirection(forward);
  const right = new THREE.Vector3().setFromMatrixColumn(camera.matrixWorld, 0);
  const distance = camera.position.distanceTo(controls.target);
  const speed = Math.max(12, Math.min(120, distance * 0.55));
  const [x, y] = movementVector(pressedKeys, [forward.x, forward.y], [right.x, right.y], speed, delta);
  camera.position.x += x;
  camera.position.y += y;
  controls.target.x += x;
  controls.target.y += y;
}

function updateGrids() {
  const distance = camera.position.distanceTo(controls.target);
  const step = Math.max(0.1, 10 ** Math.floor(Math.log10(Math.max(1, distance / 8))));
  gridPlanes.forEach((plane, index) => {
    plane.visible = state.view === '3d' || index === 0;
    plane.material.uniforms.uStep.value = step;
  });
}

function animate() {
  requestAnimationFrame(animate);
  const delta = Math.min(clock.getDelta(), 0.05);
  if (document.hidden) return;
  updateMovement(delta);
  controls.update();
  updateGrids();
  updateCategoryVisuals();
  renderer.render(scene, camera);
}
animate();

function frameCamera(positions = null) {
  pressedKeys.clear();
  const bounds = new THREE.Box3();
  for (const position of positions || state.layout.positions.values()) {
    bounds.expandByPoint(new THREE.Vector3(...position));
  }
  const center = bounds.isEmpty() ? new THREE.Vector3(0, 0, 42) : bounds.getCenter(new THREE.Vector3());
  const size = bounds.isEmpty() ? new THREE.Vector3(120, 120, 84) : bounds.getSize(new THREE.Vector3());
  const verticalFit = Math.max(size.y, size.x / Math.max(camera.aspect, 0.35), 40);
  if (state.view === '2d') {
    const distance = Math.max(220, verticalFit / (2 * Math.tan(THREE.MathUtils.degToRad(camera.fov / 2))) * 1.35);
    camera.up.set(0, 1, 0);
    controls.target.set(center.x, center.y, 0);
    camera.position.set(center.x, center.y, distance);
    controls.enableRotate = false;
  } else {
    const span = Math.max(verticalFit, size.z, 50);
    const distance = Math.max(180, span / (2 * Math.tan(THREE.MathUtils.degToRad(camera.fov / 2))) * 1.8);
    const offset = new THREE.Vector3(1, -1.2, 0.85).normalize().multiplyScalar(distance);
    camera.up.set(0, 0, 1);
    controls.target.copy(center);
    camera.position.copy(center).add(offset);
    controls.enableRotate = true;
  }
  controls.update();
}
frameCamera();

function disposeObject(object) {
  if (!object) return;
  object.geometry?.dispose();
  const materials = Array.isArray(object.material) ? object.material : [object.material];
  materials.filter(Boolean).forEach(material => {
    material.map?.dispose();
    material.dispose();
  });
}

function clearGroup(group) {
  while (group.children.length) {
    const child = group.children[0];
    group.remove(child);
    disposeObject(child);
  }
}

function categoryLabel(category) {
  const canvas = document.createElement('canvas');
  canvas.width = 512;
  canvas.height = 128;
  const context = canvas.getContext('2d');
  context.clearRect(0, 0, 512, 128);
  context.font = `${category.level === 1 ? 600 : 500} ${category.level === 1 ? 48 : 40}px "Microsoft YaHei", sans-serif`;
  context.textAlign = 'center';
  context.textBaseline = 'middle';
  context.fillStyle = category.level === 1 ? '#e1d7c8' : '#b8ad9d';
  context.fillText(category.level === 1 ? category.l1 : category.l2, 256, 64, 480);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  const material = new THREE.SpriteMaterial({map: texture, transparent: true, opacity: 0.88, depthWrite: false});
  const sprite = new THREE.Sprite(material);
  sprite.position.set(category.center[0], category.center[1], 0.25);
  sprite.center.set(0.5, 0);
  sprite.renderOrder = 4;
  sprite.userData = {type: 'label', level: category.level, key: category.key};
  return sprite;
}

function renderCategories() {
  clearGroup(categoryGroup);
  const visible = new Set();
  state.filtered.forEach(point => {
    visible.add(`L1:${point.category_l1 || '其他／无法判断'}`);
    visible.add(`L2:${point.category_l1 || '其他／无法判断'}/${point.category_l2 || '无法判断'}`);
  });
  state.layout.categories.filter(category => visible.has(category.key)).forEach(category => {
    const geometry = new THREE.CylinderGeometry(category.radius, category.radius, 20000, 64, 1, true);
    const material = new THREE.MeshBasicMaterial({
      color: category.level === 1 ? 0x635d54 : 0x776b57,
      transparent: true, opacity: categoryOpacity(category.level, 240),
      side: THREE.DoubleSide, depthWrite: false,
    });
    const cylinder = new THREE.Mesh(geometry, material);
    cylinder.rotation.x = Math.PI / 2;
    cylinder.position.set(category.center[0], category.center[1], controls.target.z);
    cylinder.renderOrder = 0;
    cylinder.userData = {type: 'volume', level: category.level, key: category.key};
    categoryGroup.add(cylinder);
    categoryGroup.add(categoryLabel(category));
  });
  updateCategoryVisuals();
}

function updateCategoryVisuals() {
  categoryGroup.visible = Boolean(document.querySelector('[data-layer="categories"]')?.checked);
  const selectedL2 = state.selectedPoint ? `L2:${state.selectedPoint.category_l1}/${state.selectedPoint.category_l2}` : null;
  categoryGroup.children.forEach(object => {
    const distance = camera.position.distanceTo(object.position);
    if (object.userData.type === 'volume') {
      object.position.z = controls.target.z;
      object.visible = state.view === '3d';
      object.material.opacity = categoryOpacity(object.userData.level, distance);
    } else {
      const worldHeight = 2 * distance * Math.tan(THREE.MathUtils.degToRad(camera.fov / 2));
      const height = THREE.MathUtils.clamp(worldHeight * 0.04, 2.5, 13);
      object.scale.set(height * 4, height, 1);
      object.visible = state.view === '3d' && (object.userData.level === 1 || distance < 150 || object.userData.key === selectedL2);
    }
  });
}

function renderUserLegend() {
  const users = [...new Set(state.filtered.map(point => point.user_pseudonym || '未知用户'))].sort();
  const compared = new Set(buildAnalyzableComparisonGroups(state.filtered)
    .filter(group => !state.selectedProduct || group.productKey === state.selectedProduct)
    .flatMap(group => [group.userA, group.userB]));
  $('userLegend').innerHTML = users.length ? users.map(user => {
    const color = userColor(user === '未知用户' ? '' : user);
    const weight = compared.has(user) ? 'font-weight:700' : '';
    return `<span style="color:${color};${weight}">● ${esc(user)}</span>`;
  }).join('') : '暂无可见用户';
}

function renderScene() {
  if (pointCloud) {
    scene.remove(pointCloud);
    disposeObject(pointCloud);
    pointCloud = null;
  }
  const points = state.filtered;
  $('emptyState').hidden = points.length > 0;
  renderCategories();
  $('edgeMeta').textContent = `${state.data.edges.length} 条后台关系候选`;
  if (!points.length) {
    renderUserLegend();
    return;
  }
  const positions = new Float32Array(points.length * 3);
  const colors = new Float32Array(points.length * 3);
  const sizes = new Float32Array(points.length);
  const alphas = new Float32Array(points.length);
  const borders = new Float32Array(points.length);
  points.forEach((point, index) => {
    const coordinate = state.layout.positions.get(point.observation_id) || [0, 0, 0];
    const position = [coordinate[0], coordinate[1], state.view === '2d' ? 0 : coordinate[2]];
    positions.set(position, index * 3);
    const color = new THREE.Color(userColor(point.user_pseudonym));
    colors.set([color.r, color.g, color.b], index * 3);
    const selected = !state.selectedProduct || state.selectedProduct === point.product_key;
    sizes[index] = state.selectedPoint?.observation_id === point.observation_id ? 15 : selected ? 9 : 5;
    alphas[index] = selected ? 0.94 : 0.10;
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
  pointCloud.renderOrder = 10;
  scene.add(pointCloud);
  renderUserLegend();
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

function comparisonPosition(point) {
  const coordinate = state.layout.positions.get(point.observation_id) || [0, 0, 0];
  return [coordinate[0], coordinate[1], state.view === '2d' ? 0 : coordinate[2]];
}

function addComparisonLink(line, color) {
  const from = new THREE.Vector3(...line.from);
  const to = new THREE.Vector3(...line.to);
  const length = from.distanceTo(to);
  if (!Number.isFinite(length) || length < 1e-6) return;
  const geometry = new THREE.BufferGeometry().setFromPoints([from, to]);
  const material = new THREE.LineBasicMaterial({color, transparent: true, opacity: 0.9, depthWrite: false});
  const link = new THREE.Line(geometry, material);
  link.renderOrder = 4;
  link.userData.type = 'comparison-link';
  comparisonGroup.add(link);
}

function renderComparison() {
  clearGroup(comparisonGroup);
  comparisonGroup.visible = Boolean(document.querySelector('[data-layer="comparison"]')?.checked);
  const groups = buildAnalyzableComparisonGroups(state.filtered)
    .filter(group => !state.selectedProduct || group.productKey === state.selectedProduct);
  const framingPositions = [];
  const cards = [];
  for (const group of groups) {
    const result = comparePriceGroups(
      {name: group.userA, prices: group.pointsA.map(point => point.normalized_price_cents / 100)},
      {name: group.userB, prices: group.pointsB.map(point => point.normalized_price_cents / 100)},
    );
    if (result.conclusion === 'nodata') continue;
    const descriptor = buildComparisonGeometry(group.points, comparisonPosition);
    const color = {red: 0xe46755, yellow: 0xeaae35, green: 0x72b5aa}[result.conclusion];
    descriptor.treeLines.forEach(line => addComparisonLink(line, color));
    framingPositions.push(...group.points.map(comparisonPosition));
    const percent = Number.isFinite(result.diffPct) ? `${result.diffPct.toFixed(2)}%` : '∞';
    const conclusion = {red: '严重疑似', yellow: '关注／低置信', green: '未见明显差异'}[result.conclusion];
    const colorHex = color.toString(16).padStart(6, '0');
    cards.push(`<div class="stat-card" style="border-left:3px solid #${colorHex}"><strong style="color:#${colorHex}">${esc(group.productName)} · ${conclusion}</strong><br><span style="color:${userColor(group.userA)}">● ${esc(group.userA)}</span> ↔ <span style="color:${userColor(group.userB)}">● ${esc(group.userB)}</span><br>均价差 ${esc(formatPrice(result.diff * 100))}（${percent}）；${group.pointsA.length} / ${group.pointsB.length} 个有效点<br><small>${esc(result.reason)}</small><br><small>${descriptor.treeLines.length} 条组内最小树细线。</small></div>`);
  }
  if (framingPositions.length) frameCamera(framingPositions);
  $('comparison').innerHTML = cards.length
    ? `${cards.join('')}<div>共享口径：关注 ≥5 元且 ≥5%；严重 ≥10 元且 >20%，两侧各 ≥3。</div>`
    : '当前筛选与商品选择下，没有具备两位有效用户及折算价的可分析商品组。';
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
  state.layout = buildSemanticLayout(data.points || [], data.category_taxonomy || {});
  state.mock = mock;
  state.selectedPoint = null;
  state.selectedProduct = null;
  renderDetail();
  populateControls();
  renderMeta();
  frameCamera();
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
  if (view !== 'table') { resize(); frameCamera(); }
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

function editableTarget(target) {
  return target instanceof HTMLElement && (target.matches('input,select,textarea,[contenteditable="true"]') || target.closest('[contenteditable="true"]'));
}
window.addEventListener('keydown', event => {
  if (!['2d', '3d'].includes(state.view) || editableTarget(event.target) || event.ctrlKey || event.metaKey || event.altKey) return;
  const key = event.key.toLowerCase();
  if (!['w', 'a', 's', 'd'].includes(key)) return;
  pressedKeys.add(key);
  event.preventDefault();
});
window.addEventListener('keyup', event => pressedKeys.delete(event.key.toLowerCase()));
window.addEventListener('blur', () => pressedKeys.clear());
document.addEventListener('visibilitychange', () => {
  pressedKeys.clear();
  if (document.hidden && state.playing) stopPlay();
});

['platformFilter','categoryFilter','userFilter','cityFilter','promoFilter','gapFilter','searchInput'].forEach(id => {
  $(id).addEventListener(id === 'searchInput' || id === 'userFilter' || id === 'cityFilter' ? 'input' : 'change', applyFilters);
});
['startTime','endTime'].forEach(id => $(id).addEventListener('change', applyFilters));
document.querySelectorAll('[data-layer]').forEach(input => input.addEventListener('change', applyFilters));
document.querySelectorAll('[data-view]').forEach(button => button.addEventListener('click', () => switchView(button.dataset.view)));
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
