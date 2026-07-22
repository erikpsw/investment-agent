---
name: gf_etf_super_fund
description: 广发证券 ETF 超级资金异动查询。支持查询发生大幅流入、大幅流出、持续流入、持续流出等资金异动的 ETF 列表及近 14 日资金明细。
user-invocable: true
metadata:
  provider: 广发证券
  requires:
    env: ["GF_SKILLS_APIKEY"]
    bins: ["python"]
---

# 广发证券 ETF 超级资金异动 Skill

当用户需要跟踪 ETF 资金异动、观察市场情绪、识别短期资金聚焦方向时使用。

## 工具

### etfSuperFund

参数：
- `type`：异动类型，固定为 `大幅流入`、`大幅流出`、`持续流入`、`持续流出`

执行：

```bash
python gf_etf_super_fund.py etfSuperFund --type 大幅流入
```

底层接口：
- `service_name`: `etf-super-fund`
- `tool_name`: `gfmiddle_eits_super_fund_etf_superfund_get`

关键字段包括 `etfcode`、`etfname`、`mktCd`、`tradeDate`、`fndNet`、`fndNetPercent`、`estimatedFundingCost`、`capitalProfitMargin`、`details[].tradeDate`、`details[].fndNetIn`。
