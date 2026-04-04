from typing import Any
from .state import InvestmentState
from .llm import get_llm_client
from ..data import StockFetcher
from .tools.report_analyzer import analyze_financial_report, get_latest_analysis
from .tools.pdf_analyzer import analyze_pdf_report, get_cached_reports


fetcher = StockFetcher()


def analyze_fundamentals(state: InvestmentState) -> dict[str, Any]:
    """基本面分析节点
    
    分析内容：
    - 财务指标（ROE、利润率、资产周转率等）
    - 盈利能力
    - 成长性
    - 估值水平
    """
    ticker = state.get("ticker", "")
    if not ticker:
        return {"errors": ["缺少股票代码"]}
    
    try:
        financials = fetcher.get_financials(ticker)
        key_metrics = fetcher.get_key_metrics(ticker)
        
        if "error" in key_metrics:
            return {
                "financials": {},
                "key_metrics": {},
                "errors": [f"获取财务数据失败: {key_metrics['error']}"],
            }
        
        llm = get_llm_client()
        analysis = llm.analyze(
            data={
                "ticker": ticker,
                "key_metrics": key_metrics,
            },
            task="对该股票进行基本面分析，评估其盈利能力、成长性、财务健康度和估值水平",
            format_hint="""请按以下格式输出：
## 盈利能力
...

## 成长性
...

## 财务健康度
...

## 估值水平
...

## 综合评价
..."""
        )
        
        return {
            "financials": {
                k: v.to_dict() if hasattr(v, "to_dict") else str(v)
                for k, v in financials.items()
            },
            "key_metrics": key_metrics,
            "messages": [{
                "role": "fundamental_agent",
                "content": analysis,
            }],
        }
        
    except Exception as e:
        return {"errors": [f"基本面分析失败: {str(e)}"]}


def get_financial_summary(state: InvestmentState) -> dict[str, Any]:
    """获取财务摘要（轻量版，不调用 LLM）"""
    ticker = state.get("ticker", "")
    if not ticker:
        return {"errors": ["缺少股票代码"]}
    
    try:
        key_metrics = fetcher.get_key_metrics(ticker)
        
        if "error" in key_metrics:
            return {"errors": [f"获取财务数据失败: {key_metrics['error']}"]}
        
        summary = {
            "ticker": ticker,
            "profitability": {
                "roe": key_metrics.get("roe"),
                "roa": key_metrics.get("roa"),
                "profit_margin": key_metrics.get("profit_margin"),
                "gross_margin": key_metrics.get("gross_margin"),
            },
            "valuation": {
                "pe_ratio": key_metrics.get("pe_ratio"),
                "pb_ratio": key_metrics.get("pb_ratio"),
            },
            "leverage": {
                "debt_to_equity": key_metrics.get("debt_to_equity"),
                "current_ratio": key_metrics.get("current_ratio"),
            },
        }
        
        return {
            "key_metrics": key_metrics,
            "messages": [{
                "role": "fundamental_agent",
                "content": f"财务摘要: {summary}",
            }],
        }
        
    except Exception as e:
        return {"errors": [f"获取财务摘要失败: {str(e)}"]}


def ai_report_analysis(state: InvestmentState) -> dict[str, Any]:
    """AI 财报分析工具 - 提取关键财务数据
    
    使用 AI 分析财报数据，提取：
    - 营收和利润
    - 财务亮点
    - 风险因素
    - 业绩展望
    - 投资建议
    """
    ticker = state.get("ticker", "")
    stock_name = state.get("stock_name", "")
    if not ticker:
        return {"errors": ["缺少股票代码"]}
    
    try:
        cached = get_latest_analysis(ticker)
        if cached and "error" not in cached:
            summary = cached.get("summary", "")
            recommendation = cached.get("recommendation", "")
            outlook = cached.get("outlook", "")
            
            highlights_text = ""
            for h in cached.get("highlights", []):
                highlights_text += f"- {h['metric']}: {h['value']}"
                if h.get("change"):
                    highlights_text += f" ({h['change']})"
                if h.get("comment"):
                    highlights_text += f" - {h['comment']}"
                highlights_text += "\n"
            
            risks_text = ""
            for r in cached.get("risks", []):
                severity_cn = {"high": "高", "medium": "中", "low": "低"}.get(r["severity"], r["severity"])
                risks_text += f"- [{severity_cn}风险] {r['category']}: {r['description']}\n"
            
            content = f"""## AI 财报分析结果

**总结**: {summary}

**投资建议**: {recommendation or "暂无"}

### 财务亮点
{highlights_text or "暂无数据"}

### 风险提示
{risks_text or "暂无风险提示"}

### 业绩展望
{outlook or "暂无展望信息"}

分析时间: {cached.get('analysis_date', '')[:10]}
置信度: {int(cached.get('confidence', 0.5) * 100)}%
"""
            
            return {
                "report_analysis": cached,
                "messages": [{
                    "role": "report_analyzer",
                    "content": content,
                }],
            }
        
        import akshare as ak
        code = ticker.replace("sh", "").replace("sz", "").replace("SH", "").replace("SZ", "")
        financial_data = {}
        
        try:
            df = ak.stock_financial_abstract_ths(symbol=code)
            if df is not None and not df.empty:
                financial_data["latest"] = df.iloc[-1].to_dict()
                if len(df) > 1:
                    financial_data["previous"] = df.iloc[-2].to_dict()
        except Exception:
            pass
        
        if not financial_data:
            return {
                "errors": ["无法获取财务数据"],
                "messages": [{
                    "role": "report_analyzer",
                    "content": "无法获取财务数据，请稍后重试",
                }],
            }
        
        result = analyze_financial_report(
            ticker=ticker,
            stock_name=stock_name or ticker,
            financial_data=financial_data,
            report_type="年报",
        )
        
        if "error" in result:
            return {
                "errors": [result["error"]],
                "messages": [{
                    "role": "report_analyzer",
                    "content": f"分析失败: {result['error']}",
                }],
            }
        
        summary = result.get("summary", "")
        recommendation = result.get("recommendation", "")
        outlook = result.get("outlook", "")
        
        highlights_text = ""
        for h in result.get("highlights", []):
            if isinstance(h, dict):
                highlights_text += f"- {h['metric']}: {h['value']}"
                if h.get("change"):
                    highlights_text += f" ({h['change']})"
                if h.get("comment"):
                    highlights_text += f" - {h['comment']}"
                highlights_text += "\n"
        
        risks_text = ""
        for r in result.get("risks", []):
            if isinstance(r, dict):
                severity_cn = {"high": "高", "medium": "中", "low": "低"}.get(r["severity"], r["severity"])
                risks_text += f"- [{severity_cn}风险] {r['category']}: {r['description']}\n"
        
        content = f"""## AI 财报分析结果

**总结**: {summary}

**投资建议**: {recommendation or "暂无"}

### 财务亮点
{highlights_text or "暂无数据"}

### 风险提示
{risks_text or "暂无风险提示"}

### 业绩展望
{outlook or "暂无展望信息"}

分析时间: {result.get('analysis_date', '')[:10]}
置信度: {int(result.get('confidence', 0.5) * 100)}%
"""
        
        return {
            "report_analysis": result,
            "messages": [{
                "role": "report_analyzer",
                "content": content,
            }],
        }
        
    except Exception as e:
        return {"errors": [f"AI财报分析失败: {str(e)}"]}


def pdf_report_analysis(state: InvestmentState) -> dict[str, Any]:
    """PDF 财报深度分析工具
    
    下载、解析 PDF 财报，提取关键信息进行 AI 分析。
    自动缓存已下载的 PDF，避免重复下载。
    """
    ticker = state.get("ticker", "")
    stock_name = state.get("stock_name", "")
    if not ticker:
        return {"errors": ["缺少股票代码"]}
    
    try:
        import akshare as ak
        
        code = ticker.replace("sh", "").replace("sz", "").replace("SH", "").replace("SZ", "")
        
        try:
            df = ak.stock_notice_report(symbol=code)
            if df is None or df.empty:
                return {
                    "errors": ["未找到财报公告"],
                    "messages": [{
                        "role": "pdf_analyzer",
                        "content": "未找到该股票的财报公告",
                    }],
                }
        except Exception as e:
            return {
                "errors": [f"获取财报列表失败: {str(e)}"],
                "messages": [{
                    "role": "pdf_analyzer",
                    "content": f"获取财报列表失败: {str(e)}",
                }],
            }
        
        annual_reports = df[df["公告标题"].str.contains("年度报告|年报", na=False)]
        if annual_reports.empty:
            annual_reports = df.head(3)
        
        if annual_reports.empty:
            return {
                "errors": ["未找到年报"],
                "messages": [{
                    "role": "pdf_analyzer",
                    "content": "未找到年度报告",
                }],
            }
        
        latest = annual_reports.iloc[0]
        report_title = latest.get("公告标题", "财报")
        pdf_url = latest.get("公告链接", "") or latest.get("url", "")
        
        if not pdf_url:
            return {
                "errors": ["未找到 PDF 链接"],
                "messages": [{
                    "role": "pdf_analyzer",
                    "content": "未找到财报 PDF 下载链接",
                }],
            }
        
        result = analyze_pdf_report(
            ticker=ticker,
            stock_name=stock_name or ticker,
            pdf_url=pdf_url,
            report_title=report_title,
        )
        
        if "error" in result:
            return {
                "errors": [result["error"]],
                "messages": [{
                    "role": "pdf_analyzer",
                    "content": f"PDF 分析失败: {result['error']}",
                }],
            }
        
        summary = result.get("summary", "")
        opinion = result.get("investment_opinion", "")
        outlook = result.get("outlook", "")
        
        financials = result.get("key_financials", {})
        financials_text = ""
        if financials:
            for k, v in financials.items():
                if v:
                    label = {
                        "revenue": "营业收入",
                        "net_profit": "净利润",
                        "gross_margin": "毛利率",
                        "net_margin": "净利率",
                        "roe": "ROE",
                        "eps": "每股收益",
                    }.get(k, k)
                    financials_text += f"- {label}: {v}\n"
        
        highlights_text = ""
        for h in result.get("business_highlights", []):
            if h:
                highlights_text += f"- {h}\n"
        
        breakdown_text = ""
        for seg in result.get("revenue_breakdown", []):
            if isinstance(seg, dict):
                breakdown_text += f"- {seg.get('segment', '')}: {seg.get('revenue', '')} ({seg.get('ratio', '')}) {seg.get('growth', '')}\n"
        
        risks_text = ""
        for r in result.get("risks", []):
            if isinstance(r, dict):
                level_cn = {"high": "高", "medium": "中", "low": "低"}.get(r.get("level", ""), "")
                risks_text += f"- [{level_cn}风险] {r.get('type', '')}: {r.get('description', '')}\n"
        
        content = f"""## PDF 财报深度分析

**报告**: {report_title}

**总结**: {summary}

**投资建议**: {opinion or "暂无"}

### 关键财务数据
{financials_text or "暂无数据"}

### 业务亮点
{highlights_text or "暂无"}

### 收入结构
{breakdown_text or "暂无数据"}

### 风险因素
{risks_text or "暂无风险提示"}

### 展望
{outlook or "暂无"}

---
文档长度: {result.get('text_length', 0):,} 字符
识别章节: {', '.join(result.get('sections_found', []))}
分析时间: {result.get('analysis_date', '')[:10]}
置信度: {int(result.get('confidence', 0.5) * 100)}%
"""
        
        return {
            "pdf_analysis": result,
            "messages": [{
                "role": "pdf_analyzer",
                "content": content,
            }],
        }
        
    except Exception as e:
        return {"errors": [f"PDF 财报分析失败: {str(e)}"]}
