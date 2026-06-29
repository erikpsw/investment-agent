---
name: gf_fund_detail
description: 广发证券基金详情查询。基于广发证券接口查询单只基金完整详情，包括净值、收益率、风险等级、申购赎回规则、基金经理、基金公司及综合评价等信息。
user-invocable: true
metadata:
  provider: 广发证券
  requires:
    env: ["GF_SKILLS_APIKEY"]
    bins: ["python"]
---

# 广发证券基金详情 Skill

当用户需要查询基金概况、净值、收益率、风险等级、申购赎回规则、基金经理、基金公司或综合评价时使用本 skill。

## 工具

### fundDetail

查询单只基金完整信息。

参数：
- `tradeCode`：基金交易代码，必填，如 `519002`

执行：

```bash
python gf_fund_detail.py fundDetail --tradeCode 519002
```

底层接口：
- `service_name`: `jijin_info`
- `tool_name`: `finance-api_product_fund_detail_get`

关键字段包括 `tradeCode`、`chiName`、`secuAbbr`、`fundType`、`riskLevel`、`shareNav`、`return1w`、`return1m`、`return3m`、`return6m`、`return1y`、`return3y`、`assetScale`、`fundManageCorp`、`contractEffDate`、`prodStatus`、`isAllowBuy`、`isAllowRedeem`、`min_share`、`min_share2`、`extraInfo`、`report`。

## 配置

必须设置环境变量：

```bash
GF_SKILLS_APIKEY=<apikey>
```
