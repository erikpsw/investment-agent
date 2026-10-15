# 选股页手动刷新 Actions

页面 `https://www.erikai.top/stock-picker` 的“更新行情与评分缓存”通过受保护的 `POST /api/formula-ranking/refresh` 调用固定的 main 分支工作流。需要网站 Auth0 登录；投资组合 PAT 不可使用。

在 Vercel 项目 investment-agent-api 的 Production 环境配置以下两项，再重新部署最新版本：

- `GITHUB_ACTIONS_TOKEN`：专用 fine-grained GitHub token，只选择 erikpsw/investment-agent 仓库，Actions 权限 Read and write。仅服务端使用，不添加 NEXT_PUBLIC 前缀，不提交到 Git，也不要发到聊天。
- `GITHUB_ACTIONS_ADMIN_SUBS`：允许操作的 Auth0 用户 sub，多个值用逗号分隔。本人登录网站后，可从 `/auth/profile` 返回的用户信息取得自己的 sub。

未登录返回 401；非管理员返回 403；未配置 GitHub 凭据返回 503。已排队或运行的工作流直接复用，不重复提交。任务完成后还需等待缓存提交的 Vercel 部署，再刷新页面。

当前 Vercel 连接器查看环境变量返回 403，无法代为确认或配置上述变量。部署状态查看仍可用。

## A 股降级状态

定时更新依次尝试新浪报价和腾讯批量报价。腾讯使用保存的沪深主板目录重新获取每只股票的原始报价，不复用旧价格或估值；来源文案明确目录范围，覆盖不足 95% 或低于 2500 只时拒绝保存。

按北京时间最近完成交易日校验，避免排队跨午夜误判。供应商不可用但保存报价仍有效时，保留文件并明确输出降级 warning；报价也已过期时任务仍失败。不会把缓存日期改成抓取日期。
