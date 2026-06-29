---
name: gf_lhb_list
description: 广发证券龙虎榜个股列表查询。支持查询指定交易日、指定市场的龙虎榜异常交易个股列表，返回上榜原因、成交额、涨跌幅等关键信息。
user-invocable: true
metadata:
  provider: 广发证券
  requires:
    env: ["GF_SKILLS_APIKEY"]
    bins: ["python"]
---

# 广发证券龙虎榜个股列表 Skill

当用户需要定位指定交易日龙虎榜个股、分析上榜原因或复盘市场情绪时使用。

## 工具

### lhbList

参数：
- `date`：日期，整数，格式 `YYYYMMDD`，如 `20260313`
- `market`：市场，`sh` 或 `sz`

执行：

```bash
python gf_lhb_list.py lhbList --date 20260313 --market sh
```

底层接口：
- `service_name`: `lhb`
- `tool_name`: `lhb_aborttrade_market_date_get`

关键字段包括 `trdCode`、`secuSht`、`clsPrc`、`dayChgRat`、`tnvVol`、`tnvVal`、`items[].rsnSht`、`items[].rsnCode`、`items[].beginDate`、`items[].endDate`。
