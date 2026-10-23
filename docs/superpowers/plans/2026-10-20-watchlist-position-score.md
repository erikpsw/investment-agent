# Watchlist and Position Score Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为现有自选和持仓接入可追溯评分历史、买入基准、仓位预算与用户确认的保护计划。

**Architecture:** 复用共享公式和个股详情数据提供器，新增用户作用域的检测服务、纯风险计算模块与事务存储。评分历史与交易事件独立持久化；组合、现金和事件变更通过一个数据库事务提交。两个现有页面使用共享检测组件，自动刷新不改变交易或确认保护价。

**Tech Stack:** Python/FastAPI/Pydantic、PostgreSQL/Supabase、Next.js 16.2.2/React 19.2.4/TypeScript，沿用现有测试工具与依赖。

**Spec:** `docs/superpowers/specs/2026-10-20-watchlist-position-score-design.md`

**Execution:** 当前聊天中由主执行者逐项完成。用户已要求开始执行；本文件是该设计对应的具体实施清单，审阅后连续执行，不在各任务之间再次确认。用户工作区已有大量修改，保留既有工作；本计划不包含提交、推送或生产发布。

## Global Constraints

- CN/HK/US均支持，按市场和规范化代码联合标识，不能只凭字符串前缀推断市场。
- 页面可见时每60秒检查一次；页面隐藏和退出时停止，不创建持续后台作业。
- 默认最近30个交易日，可展开90日，固定每次返回上限并支持分页。
- 买入机会评分复用现有共享公式；不推广此前研究候选权重，不输出盈利概率。
- 不补造买入时评分；仅相同公式版本、模式、配置指纹直接计算分差。
- 风险约束优先；持久化失败不伪报成功；候选保护计划与已确认计划分开。
- 同币种同尺度的已确认止损只能保持或收紧；清仓重买建立新持仓生命周期。
- 页面仅提供检测、记账和操作参考，不连接券商下单。
- 云端变更遵循Supabase技能和现有后台凭证模式，RLS、权限和函数调用权限一并测试；不打印凭证。
- `web/AGENTS.md`要求编码前阅读本地Next.js相关文档，不按旧版本惯例改动。

## Review Focus

- 同代码跨市场及跨用户：历史、交易事件和确认保护价均不能串用，Task 1/2/4验证。
- 缓存返回同一/更旧报价以及覆盖率变化：不伪造新趋势，不覆盖新数据，Task 1验证。
- 补录、清仓再买、首次买入无评分：基准状态正确且现金/事件原子提交，Task 2/4验证。
- 并发买入、重复请求、旧客户端整表保存：不重复扣现金或擦除服务端管理状态，Task 2/4验证。
- 跨币种、未知止损、拆股和不足一手：不生成无法核验的预算/保护价格结论，Task 3/5验证。

## Task 1: 共享个股评分与历史比较

**Files:** Create `data/security_scoring.py`, `data/score_tracking.py`, `tests/test_score_tracking.py`; modify `api/routes/formula_ranking.py`。

**Interfaces:**
- `score_security(market: str, ticker: str, mode: str) -> dict`：把现有`formula_stock_score`的数据组装移入服务层，路由继续复用同一提供器；返回与现有个股评分一致的分数、贡献和风险计划。
- `compare_score_history(current: dict, records: list[dict], entry: dict | None) -> dict`：返回可比性、上次/买入分差、5/20交易日实际观察变化、按贡献差排序的原因和质量变化。
- `ScoreTrackingService.detect(user_id, securities, mode, request_id)`：依赖注入的评分提供器与存储；返回逐项结果、保存状态和单项错误。

- [ ] 先写失败测试：同一公式记录70→75返回分差5；跨模式/版本/配置返回不可比且无分差；历史不足标明实际跨度；覆盖率改变产生独立质量原因。
- [ ] 运行 `python -m pytest tests/test_score_tracking.py -q`，确认失败来自缺失行为。
- [ ] 抽取共享提供器，保留现有个股评分契约与市场身份核验，不从热门候选池查找自选证券。
- [ ] 实现来源时间去重、乱序保护、按市场交易日期聚合、每证券失败隔离；结果来源时间未前进不追加相同历史。
- [ ] 验证空记录、陈旧报价、同代码跨市场、来源失败、保存失败和相同报价时间输入冲突；运行新增及既有个股评分测试。

## Task 2: 用户历史、持仓事件与事务存储

**Files:** Create `data/score_tracking_store.py`, `supabase/migrations/202610200001_score_tracking.sql`, `supabase/tests/score_tracking.sql`, `tests/test_score_tracking_store.py`; modify `data/portfolio_store.py`。

**Interfaces:**
- `ScoreTrackingStore.append_snapshot(owner, snapshot) -> dict`、`history(owner, market, ticker, cursor, limit, trading_days) -> dict`，只返回当前用户数据；唯一键包含用户、市场、代码、模式、配置和报价时间。
- `PortfolioStore.apply_event(owner, request_id, expected_revision, event) -> dict`：原子提交事件、持仓、现金与本轮管理状态，返回文档修订号和事件。
- `PortfolioStore.confirm_protection(owner, market, ticker, episode_id, expected_revision, plan) -> dict`：校验持仓生命周期后原子确认。
- `PortfolioStore.save_risk_settings(owner, settings) -> dict`：保存校验后的风险设置；测试使用同契约的内存实现。

- [ ] 先写失败测试：用户隔离、记录去重与乱序、同名跨市场、分页稳定、深拷贝隔离和修订号冲突。
- [ ] 运行 `python -m pytest tests/test_score_tracking_store.py -q`，确认失败后实现存储协议与内存实现。
- [ ] 新增评分记录、事件、管理状态和风险设置表；为持仓文档增加修订号，旧记录评分基准和保护状态保持缺失。
- [ ] 编写数据库函数 `apply_portfolio_event(p_owner text, p_request_id uuid, p_expected_revision bigint, p_event jsonb)`；锁定用户持仓行，使用numeric计算现金/成本，验证数量、余额及唯一幂等键，再一次性写事件和状态。
- [ ] 保护确认在同一用户持仓锁下验证生命周期、修订号、币种和尺度，不接受过期确认覆盖新计划。
- [ ] 新表/序列/函数显式授予后台角色必要权限，撤销匿名/普通前端直接写入，启用RLS；RPC仅供现有已认证后端调用。
- [ ] SQL测试覆盖重复请求、并发修订冲突、扣款失败回滚、清仓重买及无权限角色访问；使用测试数据库运行 `supabase test db`，再运行存储测试。远程环境实际核验与本地测试结论分别记录。

## Task 3: 仓位预算与保护状态纯计算

**Files:** Create `data/position_management.py`, `tests/test_position_management.py`; reuse `data/formula_risk.py`。

**Interfaces:**
- `risk_overview(positions, cash, settings, fx, detections, management) -> dict`：输出组合预算、未知风险项以及逐证券当前/目标上限/可追加数量。
- `protection_candidate(confirmed, fresh_plan, episode, price_context) -> dict`：仅返回候选或不可比较原因，不持久化。
- `position_signal(detection, history_change, budget, protection) -> dict`：返回优先状态与完整原因，评分不直接映射固定仓位。

- [ ] 先写失败测试：现价100、止损95、数量100的计划价格风险为500；风险未知不能算零；已有持仓从单股剩余额度扣除。
- [ ] 测试跨币种换算缺失、现金/费用约束、组合风险上限未设、港股每手未知、不足一手和卖出触发优先于高评分。
- [ ] 运行 `python -m pytest tests/test_position_management.py -q`，确认失败后实现Decimal计算和输入校验。
- [ ] 沿用现有模式参数作为初始参考；组合风险上限未设置时不生成预算充分判断。
- [ ] 实现同币种同尺度保护价只收紧；拆股尺度不明暂停比较；候选更新不改变已确认值。
- [ ] 测试陈旧行情、负数/NaN/无穷值、清仓生命周期失配和止盈比例的交易单位取整；运行纯计算与既有`test_formula_risk.py`测试。

## Task 4: 鉴权API与持仓记账接入

**Files:** Create `api/routes/score_tracking.py`, `tests/test_score_tracking_api.py`, `tests/test_portfolio_score_events.py`; modify `api/main.py`, `api/routes/portfolio.py`, `data/portfolio.py`。

**Interfaces:**
- `POST /api/watchlists/detection`：模式、最多50个市场/代码对象、UUID请求键；仅允许当前用户自选或持仓证券，返回逐项状态。
- `GET /api/securities/{market}/{ticker}/score-history`：30/90交易日、游标和1—200条分页。
- `GET /api/portfolio/risk-overview`：只读组合及逐持仓参考。
- `PUT /api/portfolio/risk-settings`、`PUT /api/portfolio/positions/{market}/{ticker}/protection`：经过现有写权限依赖校验。
- 扩展现有交易请求：`request_id`、`expected_revision`、`executed_at`、可选`score_snapshot_id`；响应附带修订号和本轮管理状态。

- [ ] 先写失败测试：未登录/权限不足、越权股票/快照、批量超限、未知市场和游标格式拒绝。
- [ ] 运行 `python -m pytest tests/test_score_tracking_api.py tests/test_portfolio_score_events.py -q`，确认失败后接入服务和`asyncio.to_thread`边界。
- [ ] 服务端校验买入关联快照的用户、证券、公式、观察时间及成交时间；补录不借用当前分数，缺评分仍可记账。
- [ ] 初次买入保存基准，加仓保存独立事件，部分卖出不重置本轮，清仓再买创建新一轮。
- [ ] 将交易入口切换到事务存储。对已启用管理状态的旧整表写入，没有有效修订号则返回409并保留数据；新的页面总是回传修订号。旧持仓数据本身继续可读。
- [ ] 运行鉴权、持仓、自选和新API测试，确认初始持仓迁移、失败回滚及旧数据展示兼容。

## Task 5: 自选与持仓页面

**Files:** Create `web/src/components/security-score-monitor.tsx`, `web/src/components/position-management-panel.tsx`, `web/src/lib/score-tracking.ts`, `web/tests/score-tracking.test.ts`; modify `web/src/lib/api.ts`, `web/src/components/watchlist-group-card.tsx`, `web/src/app/portfolio/page.tsx`。

**Interfaces:**
- API类型分别定义`ScoreSnapshot`、`ScoreChange`、`PositionManagement`、`PortfolioRiskOverview`；快照时间、确认时间及缺失状态保持可区分。
- `SecurityScoreMonitor`接收市场/代码集合及模式，手动检测/可关闭60秒轮询；跨分组同证券复用结果。
- `PositionManagementPanel`展示本轮买入基准、当前评分、预算、保护价与候选确认，接入现有持仓记账后的刷新。

- [ ] 阅读 `web/node_modules/next/dist/docs/`中当前客户端组件和数据获取文档，遵循`web/AGENTS.md`；不新增依赖。
- [ ] 先写失败的前端逻辑测试：旧请求不覆盖新模式/新用户状态；缺失值不显示为0；跨版本分差和保护确认状态不混淆。
- [ ] 运行 `npx tsx --test tests/score-tracking.test.ts`，失败后实现格式化与请求状态逻辑。
- [ ] 自选列表保留原快速加载；增加检测区、分数/分差/原因和时间，展开显示实际记录曲线及分项，30/90日切换和分页。
- [ ] 页面可见时60秒刷新，隐藏/退出/卸载取消请求，模式切换重置旧状态；恢复可见刷新一次，自动轮询不记交易或确认保护。
- [ ] 持仓页增加预算设置、组合风险、买入评分、止盈比例情景、保护候选和明确确认按钮；未知汇率/每手/止损显示原因。
- [ ] 交易提交携带幂等键与修订号，重试复用同一键，成功后清除请求状态并同步刷新持仓与管理面板。
- [ ] 运行前端单元测试、类型检查和相关组件lint，核对手机布局与空/加载/错误状态。

## Task 6: 集成验收与证据

**Files:** Create `web/tests/e2e/score-position-management.spec.ts`, `docs/watchlist-position-score-acceptance-20261020.md`。

- [ ] 浏览器测试覆盖自选检测、单项失败、历史展开、不同用户/模式切换、买入/加仓/清仓重买、买入基准缺失、保护候选确认和移动端。
- [ ] 运行后端相关完整测试：评分、仓位、存储、鉴权、持仓与自选；记录真实命令、通过数及任何环境限制。
- [ ] 在测试数据库核验事务和授权，不用mock通过来代替数据库事务证明；未核验的环境明确列出。
- [ ] 运行 `npm run build`及新增浏览器测试；生产参数和研究报告不受功能接入影响。
- [ ] 核对设计验收1—8，修复发现的问题；对涉及权限、事务及买入评分关联进行独立复核，取得工具支持时执行代码审查。
- [ ] 更新验收记录，区分本地实现/测试结果与云端部署状态；交付可查看的页面与文件，不把未部署状态写成已上线。

## 计划自审

六项任务覆盖设计中的评分事实、持仓生命周期、事务与权限、风险纯计算、API及两处页面。规则计算先独立测试，持久化事务单独核验，浏览器验证覆盖用户闭环。实施前仍须核对当前数据库测试环境可用性；这不会授权降低事务保证或把临时内存结果伪装为持久化成功。
