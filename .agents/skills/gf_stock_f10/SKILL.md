---
name: gf_stock_f10
description: 广发证券股票 F10 基础信息查询。支持查询个股公司全称、板块、上市日期、主营业务和所属行业等基础信息。
user-invocable: true
metadata:
  provider: 广发证券
  requires:
    env: ["GF_SKILLS_APIKEY"]
    bins: ["python"]
---

# 广发证券股票 F10 基础信息 Skill

当用户需要快速了解上市公司基本面画像、核对个股静态资料或补充投研背景信息时使用。

## 工具

### f10Basic

参数：
- `code`：证券代码，纯数字，如 `000776`
- `market`：市场，大写，`SH` 或 `SZ`

执行：

```bash
python gf_stock_f10.py f10Basic --code 000776 --market SZ
```

底层接口：
- `service_name`: `wechat_f10`
- `tool_name`: `f10_basic_post`

关键字段包括 `compName`、`boardName`、`listDate`、`businessScope`、`industries`。
