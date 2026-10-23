# 自选评分与仓位管理验收

实际实施及验收日期：2026-10-22。文件名沿用已批准计划中的路径。

本地实现和云端发布均已完成。2026-10-22新增发布阶段修复：业务冲突改用PT409、预算设置往返字段修正；最终125项后端测试通过，公网16项完整HTTP验收通过。实际迁移、域名与限制详见 `docs/score-management-deployment-20261022.md`。以下保留初始本地验收证据。迁移文件为 `supabase/migrations/202610220001_score_tracking.sql`。未迁移时新接口明确返回存储未就绪，不退回临时内存或假成功。

## 页面使用

1. 登录后打开自选股页，点击“检测评分”。同一证券跨分组复用检测结果，显示共享公式分数、上次分差、贡献原因、覆盖率和报价时间。
2. 展开历史，可选择最近30/90个实际交易观察日并分页。只有检测时保存的真实记录；历史不足时不补分。不同模式/版本/指纹的曲线断开。
3. 勾选60秒检测仅在页面可见时运行，隐藏停止、恢复可见刷新。切换模式、证券或用户会失效旧请求；自动检测不会记交易或确认保护价。
4. 在投资组合页核对单股和组合预算、买入评分、当前评分与保护计划。持仓检测跟随已保存的风险模式；修改风险模式后先保存设置。
5. 旧持仓点击“开始跟踪现有持仓”，不伪造历史买入评分。买卖与现金记账使用本币、实际成交时间和费用；没有成交前已观察的适用评分仍可记账，买入评分显示未记录。
6. 保护候选需要明确确认；本轮已确认止损只能保持或收紧。币种、生命周期或参考价格尺度不匹配时暂停使用。价格偏离原参考超过20%时采用保守暂停，可能包含正常大幅波动，需人工核对。

## 验证证据

以下命令在仓库根运行，前端命令在 `web/` 运行：

```powershell
python -m pytest tests/test_score_tracking.py tests/test_score_tracking_store.py tests/test_score_tracking_api.py tests/test_position_management.py tests/test_portfolio_score_events.py tests/test_portfolio_auth.py tests/test_portfolio_store.py tests/test_watchlists.py tests/test_watchlist_auth.py tests/test_watchlist_store.py tests/test_formula_risk.py tests/test_formula_stock_detail.py -q
node scripts/test_score_tracking_sql.mjs
```

结果：123项Python测试通过；33项真实PostgreSQL检查通过。SQL覆盖同报价冲突与去重、跨用户隔离、幂等重试、旧修订号、失败回滚、现金扣减、快照身份与观察时间、加仓/部分卖出基准不变、清仓重买、止损不能放宽、旧客户端写保护、币种与规范代码、普通角色权限拒绝。

SQL运行器使用测试目录中独立安装的 `@electric-sql/pglite`，不增加产品运行依赖。新环境可先运行：

```powershell
npm install --prefix storage/score-tracking-sql-test --no-audit --no-fund @electric-sql/pglite@0.5.11
```

```powershell
npx eslint src/components/security-score-monitor.tsx src/components/position-management-panel.tsx src/lib/score-tracking.ts
npx tsx --test tests/score-tracking.test.ts
npm run build
$env:PLAYWRIGHT_CHANNEL='chrome'
npx playwright test --config playwright.score.config.ts --workers=1 --reporter=list
```

结果：相关lint无错误或警告；4项前端逻辑测试通过；发布校验中的24项既有测试通过；Next.js生产构建（含TypeScript）通过；4项Chrome浏览器流程通过。

浏览器流程使用明确的接口fixture，证明UI行为，不代表云端真实行情或远程数据库已连通。包括手机自选检测/历史、保护显式确认与幂等记账元数据、模式切换拒绝旧请求、隐藏暂停与恢复刷新。本机3000端口属于另一项目，因此专用配置使用3107端口。已人工查看 `web/test-results/score-watchlist-mobile.png` 和 `web/test-results/score-portfolio.png`。

## 环境与边界

- Docker CLI存在，但守护进程不可用；使用PGlite真实PostgreSQL执行迁移及事务，不等同于托管Supabase完整环境。初始本地验收未执行远程迁移或部署；后续已完成云端迁移与发布，详见发布记录。未执行多连接并发压力或券商下单。
- 多连接竞争通过用户行锁及修订号设计防护；本地验证实际执行旧修订拒绝和原子回滚，不将其表述为多连接负载实测。
- 行情是供数方报价，以报价时间标注；盘中超过15分钟暂停新增趋势/建议。休市按最近常规交易时段保守校验；没有完整交易所节假日日历，长假可能显示待核验。
- 30/90范围及5/20变化依据实际有记录的观察日；缺失日期不插值，不能当作覆盖完整连续历史的回测。
- 汇率必须有可核验供数时间；缺失汇率、止损或港股每手数不按0补全，不输出无法核验的追加数量。计划价格风险不保证止损价可成交，现金与费用约束分别计算。
- 沿用共享公式与既有保护参数，没有把此前Qullamaggie研究候选权重自动晋升。此验收验证工程行为，不新增或夸大策略收益结论。
- 工作区原有改动保留；没有提交、推送或修改生产配置。
