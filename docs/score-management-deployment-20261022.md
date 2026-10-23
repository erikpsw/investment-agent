# 自选评分与仓位管理发布记录

日期：2026-10-22。用户明确要求部署，使用已有项目与授权发布工作区；未提交或推送Git。

## 发布目标与回滚点

- Vercel项目：investment-agent-api，prj_wo2tlDMBRDDLmMi3t7skPn1fZG6R。
- 本次部署：dpl_3z23syrpsZ3Vw4WYKTBZC4RyqJcV，https://investment-agent-rcfs6hcad-erikpans-projects.vercel.app 。
- 原生产部署：dpl_4gUBv5XfLUkcKkBLbQXtkXYbwnLF，https://investment-agent-3421wqw1e-erikpans-projects.vercel.app 。
- 正式域名：www.erikai.top、erikai.top。

先执行 `vercel deploy --prod --skip-domain --yes` 生成生产配置的待发布版本，通过远程检查后再promote。没有禁用部署保护或跳过失败检查。

## 数据库

Supabase Stock项目 rtivvccdqnwspbcfrrno；已执行 `watchlist_position_score_tracking` 迁移，来源为 `supabase/migrations/202610220001_score_tracking.sql`。

迁移后实际查询确认：4张新表RLS开启，anon无SELECT、authenticated无INSERT、service_role有必要权限；5项主要RPC仅service_role可执行。既有2份持仓文档均保持revision=0，没有回填或改写仓位。

在云端真实PostgreSQL以service_role执行事务检查，验证现金、买入、幂等和旧修订冲突，完整ROLLBACK，临时文档剩余0。安全advisor新增仅为4张后台专用表的“RLS开启但无前端策略”信息提示；新增对象未出现警告级安全问题，既有无关警告未修改。

回滚应用可使用原部署；数据库采用增量扩展，保留新表与事件。已进入修订管理的持仓在旧客户端上会拒绝旧式直接写入以保护数据，回滚应用不应通过关闭写入保护来强行恢复旧编辑路径。

## 构建与验收

Vercel远端24项既有评分发布测试、Next.js编译、TypeScript、18页生成和Python 3.12打包均通过，部署READY。

HTTP验收脚本：`scripts/verify_score_tracking_deployment.py`。使用随机隔离测试身份和明确标记的模拟评分，令牌只在内存及curl标准输入中传递，finally撤销令牌并清理该测试身份的全部记录。没有用真实用户持仓执行买卖或确认保护。该验收证明已部署HTTP服务与实际云数据库联通，不将模拟价格标记为真实行情。

首轮测试工具受到Windows默认GBK解码影响而失败，已改为UTF-8；第二轮在最后的冲突检查遇到curl未返回HTTP响应，未计作通过。工具增加UTF-8解析及传输错误处理，仅对GET或带幂等请求键的操作安全重试；各失败轮次的临时账户均由finally清理。

## 上线前发现并修复的PostgREST兼容问题

待发布首版在显式旧修订冲突时发生超时/503。不是仅网络抖动：以同一服务通过本地ASGI连接真实Supabase复现120秒后503，直接REST请求也超时，而直接SQL事务正常。已核对Supabase 2026-10-19官方故障说明，PostgREST 14会对自定义SQLSTATE 40001进行无限重试。

修复增加独立迁移 `20261022142807_score_tracking_http_conflicts.sql`，仅将本功能3个函数中的显式业务冲突改成PT409，保留原已应用迁移。Python存储层映射PT409为409，同时兼容真正的40001。新增失败回归后实现，33项SQL测试通过。云端实际REST验证409/PT409在1.33秒返回，未再进入循环。曾核对并尝试按精确PID终止测试循环，但查询时相关PID已退出，没有终止其他连接。

官方依据：[40001在RPC触发无限重试](https://supabase.com/docs/guides/troubleshooting/high-cpu-and-infinite-transaction-retries-when-using-custom-error-codes-in-rpc-functions-77326b)。

首版部署dpl_Ed5p3ThCWkEhcVMzSGA2hBgLnSCf未切换正式域名；修复后重新部署，以新版本完成验收后再发布。

另补充风险配置往返校验：预算概览不再把引擎内部atr_multiple混入可保存的设置，避免页面保存时被严格API模型拒绝；先复现失败测试，再修复并加入真实HTTP配置往返验收。

## 正式域名切换

已执行promote，将 www.erikai.top 与 erikai.top 的生产目标切换到 dpl_3z23syrpsZ3Vw4WYKTBZC4RyqJcV；CLI inspect www.erikai.top 已解析到新部署并确认READY。

最终修复版125项后端测试、33项真实PostgreSQL检查通过，远端24项既有发布测试、TypeScript和Next构建通过。保护部署16项HTTP验收通过，包含真实行情检测返回的明确缺失状态；证据见 `score-management-staged-checks-20261022.json`。

公网健康、自选页、持仓页均200，sh600519真实共享评分63.0、覆盖率1.0、Tencent提供可核验报价时间。Chrome实际打开正式持仓页，未登录状态正确显示登录门槛；没有使用真人账户确认保护或执行记账。

AAPL当前供数回退到Sina，时间状态为unverified_timezone；共享详情可以展示参考分数，但新的检测端按设计拒绝保存为有效观察。该保护状态不冒充实时评分可用，缺失时间不靠系统时间填补。

公网16项完整HTTP流程最终通过，包含从概览读取预算参数后直接保存、权限401/403、幂等重试、旧修订409、保护确认、清仓重买和30/90观察历史。公网真实检测同一批次AAPL与sh600519：AAPL待核验不保存，sh600519质量ok并成功保存，验证单项缺失不会阻塞有效证券。证据见 `score-management-production-checks-20261022.json` 与 `score-management-public-pages-20261022.json`。

公网首轮因本地Supabase连接TLS EOF中断，清理也一度受该本地传输错误影响；已通过独立数据库通道清理已识别的临时账户，并将工具清理改为按隔离user_id直接删除、撤销凭证优先、传输失败安全重试。早期40001循环在测试文档删除后曾迟到生成3份测试现金文档，已按3个精确测试owner清理；正式用户数据未被清理或改写。最终完整复核清理成功，临时令牌、交易、评分、持仓、自选均为0，原有2份持仓保留。

Vercel两个正式域名的alias API均确认deploymentId为 dpl_3z23syrpsZ3Vw4WYKTBZC4RyqJcV。未使用真实用户做买卖测试，没有券商下单，未提交或推送Git。
