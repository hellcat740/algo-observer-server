import * as THREE from 'three';
import { OrbitControls } from '/static/vendor/OrbitControls.js';
import { filterPoints } from './space-core.js';
import { buildComparisonGeometry } from './space-volumes.js';
import { buildAnalyzableComparisonGroups } from './space-comparison.js';
import { comparePriceGroups } from './comparison-rule.js';
import { createMockData } from './space-mock.js';
import { buildUserClusterLayout, categoryColor } from './user-space-layout.js';

const $ = id => document.getElementById(id);
const emptyData = () => ({points: [], edges: [], statistics: [], category_taxonomy: {}, platform_replication: {}, meta: {warnings: []}});
const state = {
  data: emptyData(), filtered: [], layout: buildUserClusterLayout([]),
  selectedProduct: null, selectedPoint: null, mock: false,
};

function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, char => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[char]));
}
function formatPrice(value, currency = 'CNY') {
  return Number.isFinite(value) ? `${(value / 100).toFixed(2)} ${currency}` : '—';
}
function formatTime(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '—' : date.toISOString().replace('T', ' ').replace('.000Z', 'Z');
}
function setStatus(text) { $('status').textContent = text; }

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(48, 1, 0.1, 2400);
camera.up.set(0, 0, 1);
camera.position.set(220, -260, 200);
const renderer = new THREE.WebGLRenderer({antialias: true, alpha: true});
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
renderer.setClearColor(0x17120e, 0);
$('scene').appendChild(renderer.domElement);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.08;
controls.screenSpacePanning = true;
controls.minDistance = 40;
controls.maxDistance = 1100;
controls.target.set(0, 0, 0);

const grid = new THREE.GridHelper(420, 21, 0x6f5a43, 0x493b2d);
grid.rotation.x = Math.PI / 2;
grid.position.z = -155;
grid.material.transparent = true;
grid.material.opacity = 0.22;
grid.material.depthWrite = false;
scene.add(grid);
const anchorGroup = new THREE.Group();
const comparisonGroup = new THREE.Group();
scene.add(anchorGroup, comparisonGroup);
let pointCloud = null;
const raycaster = new THREE.Raycaster();
raycaster.params.Points.threshold = 2.5;
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
  if (document.hidden) return;
  controls.update();
  renderer.render(scene, camera);
}
animate();

function disposeObject(object) {
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
function positionFor(point) {
  return state.layout.positions.get(point.observation_id) || [0, 0, 0];
}
function frameCamera() {
  if (!state.filtered.length) return;
  const bounds = new THREE.Box3();
  state.filtered.forEach(point => bounds.expandByPoint(new THREE.Vector3(...positionFor(point))));
  const center = bounds.getCenter(new THREE.Vector3());
  const size = bounds.getSize(new THREE.Vector3());
  const span = Math.max(size.x, size.y, size.z, 90);
  const distance = Math.max(240, span / (2 * Math.tan(THREE.MathUtils.degToRad(camera.fov / 2))) * 1.55);
  controls.target.copy(center);
  camera.position.copy(center).add(new THREE.Vector3(1, -1.2, 0.9).normalize().multiplyScalar(distance));
  controls.update();
}

function userLabel(user, anchor) {
  const canvas = document.createElement('canvas');
  canvas.width = 512;
  canvas.height = 128;
  const context = canvas.getContext('2d');
  context.fillStyle = 'rgba(23,18,14,0.76)';
  context.fillRect(24, 22, 464, 84);
  context.strokeStyle = 'rgba(234,174,53,0.42)';
  context.strokeRect(24, 22, 464, 84);
  context.font = '600 37px "Microsoft YaHei", sans-serif';
  context.textAlign = 'center';
  context.textBaseline = 'middle';
  context.fillStyle = '#eee5d9';
  context.fillText(user, 256, 64, 440);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({map: texture, transparent: true, depthWrite: false}));
  sprite.position.set(anchor[0], anchor[1], anchor[2] + 27);
  sprite.scale.set(42, 10.5, 1);
  sprite.renderOrder = 8;
  sprite.userData = {type: 'user-label', user};
  return sprite;
}
function renderAnchors() {
  clearGroup(anchorGroup);
  const users = [...new Set(state.filtered.map(point => String(point.user_pseudonym || '').trim() || '未知用户'))].sort();
  users.forEach(user => {
    const anchor = state.layout.anchors.get(user);
    if (anchor) anchorGroup.add(userLabel(user, anchor));
  });
  anchorGroup.visible = Boolean(document.querySelector('[data-layer="anchors"]')?.checked);
}

function renderPoints() {
  if (pointCloud) {
    scene.remove(pointCloud);
    disposeObject(pointCloud);
    pointCloud = null;
  }
  const points = state.filtered;
  $('emptyState').hidden = points.length > 0;
  if (!points.length) return;
  const positions = new Float32Array(points.length * 3);
  const colors = new Float32Array(points.length * 3);
  const sizes = new Float32Array(points.length);
  const alphas = new Float32Array(points.length);
  points.forEach((point, index) => {
    positions.set(positionFor(point), index * 3);
    const color = new THREE.Color(categoryColor(point.category_l1));
    colors.set([color.r, color.g, color.b], index * 3);
    const selected = !state.selectedProduct || state.selectedProduct === point.product_key;
    sizes[index] = state.selectedPoint?.observation_id === point.observation_id ? 14 : selected ? 9 : 5;
    alphas[index] = selected ? 0.92 : 0.08;
  });
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
  geometry.setAttribute('size', new THREE.BufferAttribute(sizes, 1));
  geometry.setAttribute('alpha', new THREE.BufferAttribute(alphas, 1));
  const material = new THREE.ShaderMaterial({
    transparent: true,
    depthWrite: false,
    vertexShader: `
      attribute vec3 color;
      attribute float size;
      attribute float alpha;
      varying vec3 vColor;
      varying float vAlpha;
      void main() {
        vColor = color; vAlpha = alpha;
        vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
        gl_PointSize = clamp(size * (220.0 / max(35.0, -mvPosition.z)), 3.0, 26.0);
        gl_Position = projectionMatrix * mvPosition;
      }`,
    fragmentShader: `
      varying vec3 vColor;
      varying float vAlpha;
      void main() {
        float radius = distance(gl_PointCoord, vec2(0.5));
        if (radius > 0.5) discard;
        float edge = smoothstep(0.34, 0.5, radius);
        gl_FragColor = vec4(mix(vColor, vec3(1.0), edge * 0.38), vAlpha);
      }`,
  });
  pointCloud = new THREE.Points(geometry, material);
  pointCloud.renderOrder = 10;
  scene.add(pointCloud);
}

function renderLegends() {
  const users = new Map();
  const categories = new Map();
  state.filtered.forEach(point => {
    const user = String(point.user_pseudonym || '').trim() || '未知用户';
    users.set(user, (users.get(user) || 0) + 1);
    const category = String(point.category_l1 || '').trim();
    categories.set(category, (categories.get(category) || 0) + 1);
  });
  $('userLegend').innerHTML = users.size ? [...users].sort(([a], [b]) => a.localeCompare(b))
    .map(([user, count]) => `<span><b>${esc(user)}</b><i>${count} 点</i></span>`).join('') : '暂无可见用户';
  $('categoryLegend').innerHTML = categories.size ? [...categories].sort(([a], [b]) => a.localeCompare(b))
    .map(([category, count]) => `<span><b style="color:${categoryColor(category)}">● ${esc(category || '未知类别')}</b><i>${count} 点</i></span>`).join('') : '暂无可见类别';
}

function pointDetails(point) {
  return `<h3>${esc(point.product_name)}</h3><dl>
    <dt>观测 ID</dt><dd>${esc(point.observation_id)}</dd>
    <dt>用户 / 类别</dt><dd>${esc(point.user_pseudonym || '未知用户')} / ${esc(point.category_l1 || '未知类别')}</dd>
    <dt>UTC 时间</dt><dd>${esc(formatTime(point.fetch_ts))}</dd>
    <dt>平台 / 卖家</dt><dd>${esc(point.platform_code)} / ${esc(point.seller_id)}</dd>
    <dt>折算价</dt><dd>${esc(formatPrice(point.normalized_price_cents))}</dd>
    <dt>优惠券</dt><dd>${esc(formatPrice(point.discount_coupon_amount_cents))}</dd>
    <dt>城市</dt><dd>${esc(point.ip_city)} / ${esc(point.shipping_city)}</dd>
    <dt>会员 / 设备</dt><dd>${esc(point.membership_level || '未知')} / ${esc(point.device_price_score_estimate ?? '未知')}</dd>
  </dl>`;
}
function renderDetail() {
  $('pointDetail').innerHTML = state.selectedPoint ? pointDetails(state.selectedPoint) : '点击数据点查看详情；点击空白处取消选择。';
}
function selectPoint(id) {
  const point = state.data.points.find(item => item.observation_id === id);
  if (!point) return;
  state.selectedPoint = point;
  state.selectedProduct = point.product_key;
  renderDetail();
  applyFilters();
}

function addComparisonLink(line, color) {
  const from = new THREE.Vector3(...line.from);
  const to = new THREE.Vector3(...line.to);
  const length = from.distanceTo(to);
  if (!Number.isFinite(length) || length < 1e-6) return;
  const geometry = new THREE.BufferGeometry().setFromPoints([from, to]);
  const material = new THREE.LineBasicMaterial({color, transparent: true, opacity: 0.45, depthWrite: false});
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
  const cards = [];
  for (const group of groups) {
    const result = comparePriceGroups(
      {name: group.userA, prices: group.pointsA.map(point => point.normalized_price_cents / 100)},
      {name: group.userB, prices: group.pointsB.map(point => point.normalized_price_cents / 100)},
    );
    if (result.conclusion === 'nodata') continue;
    const descriptor = buildComparisonGeometry(group.points, positionFor);
    const color = {red: 0xe46755, yellow: 0xeaae35, green: 0x72b5aa}[result.conclusion];
    descriptor.treeLines.forEach(line => addComparisonLink(line, color));
    const conclusion = {red: '严重疑似', yellow: '关注／低置信', green: '未见明显差异'}[result.conclusion];
    const colorHex = color.toString(16).padStart(6, '0');
    const percent = Number.isFinite(result.diffPct) ? `${result.diffPct.toFixed(2)}%` : '∞';
    cards.push(`<div class="stat-card" style="border-left:3px solid #${colorHex}"><strong style="color:#${colorHex}">${esc(group.productName)} · ${conclusion}</strong><br>${esc(group.userA)} ↔ ${esc(group.userB)}<br>均价差 ${esc(formatPrice(result.diff * 100))}（${percent}）<br><small>${esc(result.reason)}</small><br><small>${descriptor.treeLines.length} 条组内最小树半透明细线。</small></div>`);
  }
  $('comparison').innerHTML = cards.length ? cards.join('') : '当前筛选与商品选择下，没有可分析商品组。';
}

function currentFilters() {
  return {
    platform: $('platformFilter').value,
    category: $('categoryFilter').value,
    user: $('userFilter').value,
    search: $('searchInput').value,
  };
}
function applyFilters() {
  state.filtered = filterPoints(state.data.points, currentFilters());
  $('visibleCount').textContent = `${state.filtered.length} 个可见点`;
  renderPoints();
  renderAnchors();
  renderLegends();
  renderComparison();
}
function populateControls() {
  const fill = (id, values, label) => {
    const select = $(id);
    const previous = select.value;
    select.innerHTML = `<option value="">${label}</option>` + [...new Set(values.filter(Boolean))].sort()
      .map(value => `<option value="${esc(value)}">${esc(value)}</option>`).join('');
    select.value = previous;
  };
  fill('platformFilter', state.data.points.map(point => point.platform_code), '全部平台');
  fill('categoryFilter', state.data.points.map(point => point.category_l1 || ''), '全部分类');
}
function renderMeta() {
  $('dataMode').textContent = state.mock ? '演示数据' : '真实数据';
  $('dataMode').classList.toggle('mock', state.mock);
  $('pointMeta').textContent = `${state.data.points.length} 个观测点，${state.data.meta?.normalized_total || 0} 个可比价`;
  $('warnings').textContent = (state.data.meta?.warnings || []).join('；');
}
function setData(data, mock = false) {
  state.data = data;
  state.layout = buildUserClusterLayout(data.points || []);
  state.mock = mock;
  state.selectedPoint = null;
  state.selectedProduct = null;
  renderDetail();
  populateControls();
  renderMeta();
  applyFilters();
  frameCamera();
}

async function loadData() {
  const userId = localStorage.getItem('obs_user_id') || '';
  const adminKey = localStorage.getItem(window.SPACE_STORAGE_KEY) || '';
  if (!userId && !adminKey) {
    setData(emptyData());
    setStatus('请先从我的看板进入，或登录管理控制台');
    return;
  }
  const endpoint = userId ? '/api/my/space/points' : '/api/space/points';
  const headers = userId ? {'X-User-Id': userId} : {'X-API-Key': adminKey};
  setStatus('正在读取观测数据…');
  try {
    const response = await fetch(endpoint, {headers});
    if (!response.ok) throw new Error(response.status === 401 ? '登录身份已失效，请重新进入看板' : `读取失败（${response.status}）`);
    setData(await response.json(), false);
    setStatus('数据已更新');
  } catch (error) {
    setData(emptyData());
    setStatus(error.message);
  }
}

function pointerCoordinates(event) {
  const rect = renderer.domElement.getBoundingClientRect();
  pointer.x = (event.clientX - rect.left) / rect.width * 2 - 1;
  pointer.y = -(event.clientY - rect.top) / rect.height * 2 + 1;
}
renderer.domElement.addEventListener('pointerdown', event => { pointerDown = [event.clientX, event.clientY]; });
renderer.domElement.addEventListener('pointerup', event => {
  if (!pointerDown || Math.hypot(event.clientX - pointerDown[0], event.clientY - pointerDown[1]) > 5) return;
  pointerCoordinates(event);
  raycaster.setFromCamera(pointer, camera);
  const hit = pointCloud ? raycaster.intersectObject(pointCloud)[0] : null;
  if (hit) selectPoint(state.filtered[hit.index].observation_id);
  else {
    state.selectedPoint = null;
    state.selectedProduct = null;
    renderDetail();
    applyFilters();
  }
});

['platformFilter', 'categoryFilter'].forEach(id => $(id).addEventListener('change', applyFilters));
['userFilter', 'searchInput'].forEach(id => $(id).addEventListener('input', applyFilters));
document.querySelectorAll('[data-layer]').forEach(input => input.addEventListener('change', applyFilters));
$('refreshButton').addEventListener('click', loadData);
$('mockButton').addEventListener('click', () => {
  if (!state.mock && state.data.points.length) { setStatus('已有真实数据；演示模式仅在没有真实点时开放'); return; }
  setData(createMockData(), true);
  setStatus('当前全部为演示数据，不会写入数据库');
});

setData(emptyData());
loadData();
