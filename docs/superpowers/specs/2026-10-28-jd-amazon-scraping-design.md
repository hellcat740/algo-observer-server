# 京东与 Amazon.com 商品采集适配设计

## 目标

在现有浏览器插件中支持京东新版商品详情页与 Amazon.com 商品详情页。采集继续使用现有授权、自动/手动采集、脱敏、截图、本地记录、失败重试和服务端上报链路。

## 范围

- 京东：支持 `item.jd.com/<sku>.html`，保留旧版选择器并补充当前页面选择器。
- 亚马逊：支持 `www.amazon.com/dp/<ASIN>` 与 `www.amazon.com/gp/product/<ASIN>`。
- 采集商品 ID、标题、店铺/卖家、展示价、到手价、优惠、配送地、登录上下文、设备信息和截图。
- Amazon.com 使用 USD；京东使用 CNY。
- 不采集列表页、购物车、订单页，不绕过验证码或反爬验证，不读取 Cookie 值。

## 方案比较

1. **扩展现有规则驱动采集器（采用）**：在 content 与 popup 中增加/更新平台规则，复用完整采集链路，改动小且行为一致。
2. 为每个平台建立独立内容脚本：平台隔离更彻底，但会复制消息处理、等待、脱敏和上报逻辑，当前成本过高。
3. 使用通用智能提取：选择器适配少，但价格来源不可控，容易混入推荐商品价格，不适合证据型观测数据。

## 组件与数据流

1. `manifest.json` 增加 Amazon.com 主机权限、内容脚本匹配和报告页资源匹配。
2. `content/index.js`：
   - 京东增加 `.sku-title-text`、`.product-price--main`、`.top-shop-info`、`.logistics-address-main` 等当前节点。
   - Amazon 增加 ASIN 规则，以及 `#productTitle`、`#sellerProfileTriggerId`、`#corePrice_feature_div .a-price .a-offscreen`、`.a-price.a-text-price .a-offscreen` 等节点。
   - 价格只从商品主价格区域读取，避免列表和推荐区域干扰。
   - 根据平台写入 CNY 或 USD。
   - 登录判断兼容英文 `Hello, sign in`，会员识别兼容 Prime。
3. `popup/popup.js` 同步平台识别与商品 ID 规则，确保弹窗状态与内容脚本一致。
4. 服务端 `cleaning.py` 将 `amazon` 加入平台白名单；看板与本地报告补充 Amazon 名称和币种显示。
5. 后台继续使用现有 `mapObservationToBackend`，Amazon 的字符串卖家信息通过现有店铺名回退写入 `seller_id`。

## 异常处理

- 页面未加载出主价格时沿用现有限时重试；最终仍无价格则保存本地并标记未上报，不写入猜测值。
- 店铺、划线价、优惠券或配送地缺失时保存为 `null`，不影响主价格采集。
- 遇到验证码、地区跳转或非详情页时不采集。
- Amazon 推荐区域的划线价不得替代商品主价格区域；主区域现价优先于全页通用选择器。

## 测试与验收

- 自动化测试直接执行插件包中的真实 `content/index.js`，以京东和 Amazon 当前 DOM 节点夹具验证完整提取结果。
- 验证 Amazon ASIN 两种 URL、平台权限、服务端白名单和 USD 入库。
- 验证京东旧选择器仍保留，新选择器能提取标题、店铺、价格和配送地。
- 运行全部 Python 测试，并在实际京东与 Amazon.com 商品页复核关键节点。
