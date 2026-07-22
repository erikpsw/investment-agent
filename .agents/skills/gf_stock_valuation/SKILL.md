---
name: gf_stock_valuation
description: 广发证券股票市值与估值查询。支持对比多只股票总市值、PE、PB、行业均值、历史百分位，也支持对比盈利能力、资本结构、现金流和成长性等财务指标。
user-invocable: true
metadata:
  provider: 广发证券
  requires:
    env: ["GF_SKILLS_APIKEY"]
    bins: ["python"]
---

# 广发证券股票市值与估值 Skill

当用户需要横向比较股票估值、识别高估或低估标的、辅助行业估值分析，或比较两只股票财务指标时使用。

## 工具

### valuationCompare

对比多只股票总市值及估值水平。

参数：
- `stock_codes`：股票代码列表，逗号分隔，格式为交易所前缀+代码，如 `SZ000776,SH600000`

执行：

```bash
python gf_stock_valuation.py valuationCompare --stock_codes SZ000776,SZ000001
```

底层接口：
- `service_name`: `quant`
- `tool_name`: `common_basic_post`

### indicatorCompare

对比股票财务指标。

参数：
- `report_type`：报告期类型，`1`=一季报，`6`=中报，`9`=三季报，`12`=年报
- `stock_codes`：股票代码列表，逗号分隔
- `year`：报告年份，如 `2025`

执行：

```bash
python gf_stock_valuation.py indicatorCompare --report_type 9 --stock_codes SZ000783,SZ000776 --year 2025
```

底层接口：
- `service_name`: `quant`
- `tool_name`: `compare_indicator_post`
