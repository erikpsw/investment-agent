---
name: gf_etf_search
description: 广发证券 ETF 多维度筛选。支持按收益率、回撤、夏普、估值温度、规模、赛道、交易属性等条件筛选 ETF。
user-invocable: true
metadata:
  provider: 广发证券
  requires:
    env: ["GF_SKILLS_APIKEY"]
    bins: ["python"]
---

# 广发证券 ETF 多维度筛选 Skill

当用户需要寻找特定主题 ETF、做收益与风险过滤、构建 ETF 候选池时使用。

## 工具

### etfSearch

参数很多，使用 `--args` 传入 JSON 字符串，或使用常见参数：
- `search`
- `type`
- `trakType`
- `oneTrakName`
- `tradeCode`
- `tradeT0`
- `marginTrade`
- `roc1w` / `roc1m` / `roc6m` / `roc1y`
- `return1m` / `return6m` / `return1y` / `return3y`
- `maxDrawdown1m` / `maxDrawdown1y`
- `sharpRatio1y` / `sharpRatio3y`
- `valuationResult`
- `indexTempType`
- `assetScale`
- `start` / `limit`
- `sort`
- `addRealTimeRoc`

执行：

```bash
python gf_etf_search.py etfSearch --trakType 行业 --roc1m "5~" --sort -roc1m --limit 20 --addRealTimeRoc 1
```

或：

```bash
python gf_etf_search.py etfSearch --args "{\"trakType\":\"行业\",\"roc1m\":\"5~\",\"sort\":\"-roc1m\",\"limit\":20,\"addRealTimeRoc\":1}"
```

底层接口：
- `service_name`: `etf_search`
- `tool_name`: `finance_api_inclusive_etf_list_get`
