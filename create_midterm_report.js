import fs from "node:fs";
import {
  AlignmentType, Document, Footer, FootnoteReferenceRun, Header, HeadingLevel,
  Math, MathFraction, MathRun, MathSuperScript, Packer, PageNumber, Paragraph, TextRun,
  convertInchesToTwip,
} from "docx";

const outputPath = process.argv[2];
if (!outputPath) throw new Error("Usage: node create_midterm_report.js /absolute/path/output.docx");
const T = String.raw;
const font = { ascii: "Times New Roman", hAnsi: "Times New Roman", cs: "Times New Roman", eastAsia: "SimSun" };
const headingFont = { ascii: "Arial", hAnsi: "Arial", cs: "Arial", eastAsia: "Microsoft YaHei" };
const run = (text, options = {}) => new TextRun({ text, font, size: 24, ...options });
const para = (children, options = {}) => new Paragraph({
  spacing: { after: 160, line: 360 }, ...options,
  children: Array.isArray(children) ? children : [children],
});
const body = (text) => para(run(text), { indent: { firstLine: convertInchesToTwip(0.33) }, alignment: AlignmentType.JUSTIFIED });
const h1 = (text) => para(new TextRun({ text, font: headingFont, size: 32, bold: true, color: "263A3A" }), {
  heading: HeadingLevel.HEADING_1, spacing: { before: 320, after: 180 },
});
const h2 = (text) => para(new TextRun({ text, font: headingFont, size: 27, bold: true, color: "355B57" }), {
  heading: HeadingLevel.HEADING_2, spacing: { before: 260, after: 140 },
});
const eq = (children, number) => new Paragraph({
  alignment: AlignmentType.CENTER,
  spacing: { before: 100, after: 160, line: 300 },
  children: [new Math({ children }), run(`    （${number}）`, { size: 22 })],
});
const mr = (text) => new MathRun(text);
const foot = (id) => new FootnoteReferenceRun(id);
const children = [];

children.push(para(new TextRun({ text: "价衡卫士——中期报告产品介绍与展望", font: headingFont, size: 38, bold: true, color: "263A3A" }), {
  heading: HeadingLevel.TITLE, alignment: AlignmentType.CENTER, spacing: { before: 240, after: 120 },
}));
children.push(para(run("大数据价格歧视智能监测与公益诉讼维权服务平台", { size: 25, color: "526864" }), {
  alignment: AlignmentType.CENTER, spacing: { after: 360 },
}));

children.push(h1("一、产品介绍"));
children.push(h2("（一）网站创建目的"));
children.push(body(T`“价衡卫士”面向数字经济中的大数据价格歧视问题，致力于建设集价格观测、统计分析、研究展示与公益诉讼线索支持于一体的公益性服务平台。随着平台经济深入发展，同一商品或服务可能因用户画像、会员状态、设备环境等因素呈现不同价格。此类差异具有瞬时性、隐蔽性和场景依赖性，普通消费者往往只能凭个别截图或主观感受判断是否“被杀熟”，难以排除时间、地区、库存、优惠等正常定价因素，也难以形成可供复核的连续证据。`));
children.push(body(T`网站创建的核心目的，是把分散在个人浏览器中的瞬时价格信息转化为匿名、可汇聚、可检验的观测数据，将“感觉存在差别定价”推进为“有样本、有方法、有边界的统计线索”。平台并不试图直接破解平台算法或替代司法认定，而是从用户实际可见的交易结果出发，为算法歧视研究提供事实基础，为消费者协会、检察机关等公益诉讼主体发现线索、组织复测和评估公共利益损害提供技术支撑。其制度依据在于数字平等权保障、公共利益保护和个体救济失灵理论：当小额、分散、隐蔽的侵害难以通过单个消费者诉讼得到充分救济时，分布式观测与集体性证据可以成为连接个体遭遇和公益治理的桥梁。`));

children.push(h2("（二）当前网站功能"));
children.push(body(T`现阶段，网站已形成“浏览器插件采集—服务端清洗入库—用户与管理端展示—统计分析与空间可视化”的基本业务链路，主要功能如下。`));
children.push(body(T`1. 分布式价格采集。网站提供适用于 Chrome 和 Edge 的“算法歧视观测”插件，当前版本为 v1.2.0。用户在阅读知情同意并安装插件后，可在正常浏览商品页时采集本人可见的商品名称、商品链接、展示价、到手价、优惠信息、采集时间及脱敏后的浏览环境。当前插件适配淘宝、天猫、京东、拼多多和 Amazon.com，并可记录 SKU 与颜色、尺寸等已选规格，使同一商品不同规格能够分别观测，减少因规格混同造成的虚假价差。用户身份以本机随机匿名编号表示，网站不收集账号或手机号。`));
children.push(body(T`2. 数据清洗与规范化入库。服务端对平台编码、字段类型、文本长度、价格范围和采集时间进行校验，将价格统一换算为“分”存储；展示价缺失时，可在明确标注的前提下以到手价作为分析兜底。数据库同时保存商品、用户匿名引用、设备环境、城市、时段、库存提示等上下文，并保留价格节点原始文本等证据字段。跨币种观测通过每日汇率缓存折算为人民币后参与统一比较，原币记录仍予保留。`));
children.push(body(T`3. 门户与个人看板。门户提供用户看板、管理员入口和插件下载入口。用户可凭匿名编号查看自己的观测记录、统计信息和观测详情，了解个人数据贡献；个人观测空间进一步以图形方式呈现用户自身的价格序列与关联情况，增强数据采集的可理解性和参与感。`));
children.push(body(T`4. 管理控制台与研究数据管理。管理端支持观测记录检索、查看、编辑和删除，展示 SKU、已选规格与商品分类，并承担演示数据管理、数据导入导出和统计分析入口等功能。系统设置上报密钥、匿名用户编号和管理员哈希鉴权三类访问控制，区分数据上报、个人查询与研究管理权限。`));
children.push(body(T`5. 商品分类与可视化分析。系统可在上报后调用通义千问进行后台商品分类，并由每日闲时任务使用 DeepSeek 补全未分类商品；分类结果单独缓存，不改写原始观测。管理端提供二维散点图与三维观测空间，按时间、商品类别及同商品折算价相对中位数的偏差组织数据，支持筛选、搜索、旋转缩放、点选、时间播放、双用户价格序列比较和匿名 CSV 导出。三维特征模式明确采用确定性哈希投影，不将其宣称为 PCA、t-SNE 或 UMAP 等降维结果。`));
children.push(body(T`6. 疑似差别待遇筛查。统计引擎针对同一商品构造不同匿名用户之间的对比，输出描述性统计、价差幅度、显著性检验和回归结果，并以“疑似”“低置信疑似”等审慎标签提示研究线索；平台层面要求至少两个商品复现同类模式后才显示平台级疑似。所有统计输出均用于线索筛查和复测排序，不直接等同于算法歧视或违法行为的法律认定。`));

children.push(h2("（三）部署与运行情况"));
children.push(body(T`网站已由早期演示部署转向阿里云 ECS 全栈独立部署。当前架构为 FastAPI 应用与 PostgreSQL 17 数据库运行于 Docker 容器，Nginx 负责反向代理，正式域名为 algodiscriminatingcheck.cn，域名备案、DNS 解析和 HTTPS 证书均已配置，HTTP 自动跳转至 HTTPS。数据库仅通过容器内网向应用开放，不直接暴露公网端口；系统配置每日数据库备份、证书自动续期和容器自动重启，并保留与 Supabase 的每周并集同步机制作为数据冗余。线上健康检查已返回服务与数据库正常状态。现阶段服务器配置为 2 vCPU、2 GiB 内存并辅以交换空间，能够满足当前以文本观测为主的研究需求，后续扩量时需同步提升带宽、计算与存储能力。`));

children.push(h2("（四）具体实现与数据分析方法"));
children.push(body(T`平台以“同商品、可比条件、跨用户、可复现”为分析原则。首先按商品标识及必要的卖家、SKU 条件组织观测，优先使用页面展示价，分别计算各用户的价格中位数，选取价差最大的低价侧用户 A 与高价侧用户 B 构成对照。两组中位数相对价差定义为：`));
children.push(eq([
  mr("Δ = "), new MathFraction({ numerator: [mr("100(m̃_B − m̃_A)")], denominator: [mr("m̃_A")] }), mr(" %"),
], 1));
children.push(body(T`其中，m̃_A 与 m̃_B 分别为两组价格中位数。中位数能够降低极端价格和少量异常观测的影响。系统先报告样本量、均值、中位数、标准差和极值；当任一组样本不足时，仅保留描述性结果，不强行给出显著性结论。`));
children.push(body(T`在每组至少具有两条观测且样本量具备基本检验条件时，系统采用双侧 Mann–Whitney U 非参数检验，比较两组价格分布是否一致。该方法不要求价格服从正态分布，适合当前样本量有限、分布形态不明的观测数据。按低价组秩和 R_A 表示时，检验统计量为：`));
children.push(eq([
  mr("U_A = n_A n_B + "), new MathFraction({ numerator: [mr("n_A(n_A + 1)")], denominator: [mr("2")] }), mr(" − R_A"),
], 2));
children.push(body(T`检验的原假设 H₀ 为两组价格分布相同，备择假设 H₁ 为两组分布不同；显著性水平设为 α = 0.05。当 p < α 时拒绝原假设。若样本小到即使两组完全分离也无法达到显著性水平，系统会明确提示检验能力有限，而不是将“不显著”解释为“无差异”。`));
children.push(body(T`为降低城市、时段、库存、设备与平台差异等混淆因素影响，样本量达到 30 条且相关字段具有足够变异时，系统进一步建立对数价格普通最小二乘回归：`));
children.push(eq([
  mr("ln(P_i) = β_0 + β_1 D_i + γ′X_i + ε_i"),
], 3));
children.push(body(T`其中，P_i 为第 i 条观测价格，D_i 表示该观测是否来自高价侧用户 B，X_i 为城市、配送城市、峰谷时段、库存提示、设备档次估算和平台等控制变量。回归采用 HC3 异方差稳健标准误；缺失率超过 60% 或取值无变异的控制变量自动剔除。高价侧用户标签对应的近似百分比净效应为：`));
children.push(eq([
  new MathSuperScript({ children: [mr("100(e")], superScript: [mr("β_1")] }), mr(" − 1) %"),
], 4));
children.push(body(T`综合判别遵循“效应幅度＋统计显著性＋替代解释排查”的规则：当中位数价差绝对值超过 5%，且 Mann–Whitney U 检验或回归达到 p < 0.05，并且回归未显示价差可由已控制因素充分解释时，系统标记为较高置信的疑似差别待遇；小样本且无法回归时，只对超过阈值的价差给出低置信提示。同一平台至少两个商品复现后，才形成平台级疑似线索。该逻辑可用下式概括：`));
children.push(eq([
  mr("Flag = I(|Δ| > 5%) × I(p < 0.05) × I(无已识别的替代解释)"),
], 5));
children.push(body(T`此外，系统在较高置信判定成立后计算原价与到手价的中位折扣深度，对超过 10% 的情形附加“疑似假折扣模式”标签。上述阈值是当前研究筛查规则而非法律标准；观察性数据只能揭示统计关联，不能单独证明平台具有歧视意图或因果关系。`));

children.push(h2("（五）当前数据收集情况"));
children.push(para([run(T`根据项目计划书所记录的阶段性运营数据，平台已累计采集有效价格观测 3200 余条，覆盖 5 个平台。`), foot(1)]));
children.push(body(T`现有数据以“一次用户浏览所见价格”为基本观测单位，已覆盖商品标识、卖家、价格、优惠、匿名用户、设备环境、采集时间等核心维度；最新插件进一步补充 SKU 和已选规格，提高了同商品比较的准确性。商品分类缓存和汇率缓存为跨类别展示、跨币种比较提供辅助信息。网站支持数据打包导出与导入，并通过数据库备份和周期同步提高数据安全性。`));
children.push(body(T`从研究适用性看，现有数据已能够支撑功能联调、描述性分析和小规模统计验证，但样本在不同平台、商品、用户群体和时间段之间仍可能分布不均。尤其是同一商品下具备多用户、重复观测的样本，才是统计检验的有效基础；单用户或单次浏览记录主要用于展示和后续复测引导。因此，中期阶段的重点不只是增加总条数，更是提高“同商品—同规格—相近时间—多用户”对照样本的密度与字段完整度。`));

children.push(h1("二、未来展望"));
children.push(h2("（一）从规模采集转向高质量对照实验"));
children.push(body(T`下一阶段将围绕有效对照样本扩充数据，而非单纯追求观测总量。平台计划引入对照任务与众测机制，针对疑似商品组织不同匿名用户在相近时间、相同 SKU 和尽可能一致的交易条件下复测，并持续完善城市、配送距离、库存、优惠券和促销状态等字段。同步建立采集成功率、字段缺失率、重复率、跨用户覆盖率与样本时效性等质量指标，形成从线索发现、任务分发到交叉复测的闭环。平台适配范围将在维护现有电商采集稳定性的基础上，逐步扩展至外卖、在线旅游、网约车等动态定价场景。`));
children.push(h2("（二）提升统计推断的可信度与可解释性"));
children.push(body(T`统计引擎将由“价差筛查”进一步发展为“分层、稳健、可复核”的分析体系。后续将完善匹配与分层分析、效应量及置信区间展示、多重检验校正和异常值敏感性分析，并通过置换检验、留一分析和不同阈值复算检验结论稳定性。对时间间隔、地区物流、库存变化和个体优惠等替代解释，将尽可能通过准实验设计与更精细的控制变量加以排除；同时保留原始样本、参数配置和模型版本，使每一项结果均可重现。可视化将继续服务问题定位，不以复杂图形替代统计证据。`));
children.push(h2("（三）补齐法律评估与电子证据闭环"));
children.push(body(T`依托法学团队关于算法歧视构成要件、公共利益界定和公益诉讼程序构造的研究，平台将把《个人信息保护法》第 24 条、第 70 条及消费者公平交易等相关规范转化为结构化规则，建立敏感特征、差别待遇、合理抗辩和人工复核相衔接的法律评估模块。统计输出将与法律要件逐项映射，自动生成包含样本范围、方法、限制和疑似依据的初步报告，再由法学成员或合作律师复核。`));
children.push(body(T`在证据端，将逐步把页面截图、DOM 快照、原始观测、分析报告和版本信息组织为标准化证据包，计算 SHA-256 摘要并对接可信时间戳或区块链存证，形成“采集—清洗—分析—复核—固化—移交”的可审计链条。平台将坚持“统计疑似不等于法律认定”，通过人工复核和对照复测降低误报风险，最终为消费者协会、检察机关及公益律师提供可核验的线索材料，而非自动化定罪式标签。`));
children.push(h2("（四）完善安全治理与可持续运营"));
children.push(body(T`随着用户与数据规模扩大，平台将落实更严格的数据最小化、分级权限、日志审计、备份恢复和安全测试，收紧跨域访问与插件来源控制，完善用户查询、更正和删除机制。技术上将根据负载升级服务器和数据库，优化分析任务的异步执行与缓存；运营上坚持个人用户和公益组织免费使用，通过高校合作、研究委托、平台合规评估和公益资助维持服务。中长期将推动形成可复用的数据字典、采集规范与检测指标体系，探索与消费者组织、检察机关、高校和研究机构共建算法公平研究协作网络，使“价衡卫士”由项目原型成长为具有公信力的第三方算法公平观测基础设施。`));

const doc = new Document({
  features: { updateFields: false },
  footnotes: {
    1: { children: [para(run("数据来源：《价衡卫士——大数据价格歧视智能监测与公益诉讼维权服务平台项目计划书》“运营现状”。该数字为项目材料所载阶段性口径，并非实时数据库查询值。", { size: 20 }))] },
  },
  sections: [{
    properties: { page: { margin: { top: 1440, bottom: 1440, left: 1600, right: 1600 } } },
    headers: { default: new Header({ children: [para(run("价衡卫士｜中期报告产品介绍与展望", { size: 19, color: "60736F" }), { alignment: AlignmentType.CENTER })] }) },
    footers: { default: new Footer({ children: [para(new TextRun({ children: [PageNumber.CURRENT], font, size: 20 }), { alignment: AlignmentType.CENTER })] }) },
    children,
  }],
});
fs.writeFileSync(outputPath, await Packer.toBuffer(doc));
