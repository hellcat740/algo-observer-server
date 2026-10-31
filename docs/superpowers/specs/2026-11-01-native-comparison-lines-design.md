# 原生最小树细线设计

## 目标

三维观测空间中的商品最小树连线必须是真正的线，而不是视觉上仍呈柱状的圆柱网格。

## 方案比较

- 继续缩小圆柱：仍保留网格体积和相机距离缩放，不符合“真正的细线”。
- 使用粗线网格：可控制像素宽度，但仍是有体积的网格，并增加额外依赖。
- 使用 Three.js 原生 `THREE.Line`：以两个端点直接绘制线段，无体积、无额外依赖，符合需求，采用此方案。

## 改动范围

`addComparisonLink` 保留零长度边过滤，使用 `THREE.BufferGeometry` 保存起止点，`THREE.LineBasicMaterial` 保留原颜色和透明度，`THREE.Line` 加入现有比较图层。删除只服务于圆柱粗细的 `updateComparisonVisuals` 及其调用。

最小树算法、商品自动配对、红黄绿判定、取景、点选隔离、图层开关、分类圆柱和其他图层均不改变。

## 验证

静态测试断言比较连线使用 `THREE.Line`、`THREE.BufferGeometry` 和 `THREE.LineBasicMaterial`，且不再包含圆柱厚度更新。运行完整 Python 与 JavaScript 测试，再在浏览器实测三组红黄绿细线、图层开关、商品点选和 2D／3D 切换。
