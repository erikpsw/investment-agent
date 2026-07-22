---
name: gf_etf_rank
description: 广发证券 ETF 榜单查询。支持获取 ETF 涨幅、跌幅、换手、主力资金、净申购、溢价率等榜单数据。
user-invocable: true
metadata:
  provider: 广发证券
  requires:
    env: ["GF_SKILLS_APIKEY"]
    bins: ["python"]
---

# 广发证券 ETF 榜单 Skill

当用户需要筛选市场热点 ETF、观察资金偏好或获取 ETF 榜单排名时使用。

## 工具

### etfRank

参数：
- `type`：榜单类型，`1`=涨幅，`2`=跌幅，`3`=换手，`4`=主力资金，`12`=净申购，`13`=溢价率
- `page`：页数，从 `0` 开始，可选
- `size`：每页条数，可选，默认 `10`
- `sameIndexFilter`：同指数 ETF 只展示 1 只，`1`=开启，`0`=关闭，可选
- `continueRiseLimit`：连涨/连跌天数过滤，可选

执行：

```bash
python gf_etf_rank.py etfRank --type 1 --size 20
```

底层接口：
- `service_name`: `etf_rank`
- `tool_name`: `finance-api_product_etf_rank_get`
