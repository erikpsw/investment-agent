import streamlit as st
import pandas as pd
from typing import Any, Dict, List


def render_stock_card(data: Dict[str, Any]) -> None:
    """渲染股票卡片"""
    col1, col2, col3, col4 = st.columns(4)
    
    price = data.get("price", data.get("last_price"))
    change_pct = data.get("change_percent", data.get("change_pct", 0))
    
    with col1:
        st.metric(
            label=data.get("name", data.get("ticker", "N/A")),
            value=f"¥{price:.2f}" if price else "N/A",
            delta=f"{change_pct:.2f}%" if change_pct else None,
        )
    
    with col2:
        if "volume" in data:
            st.metric("成交量", format_number(data["volume"]))
    
    with col3:
        if "market_cap" in data:
            st.metric("市值", format_number(data["market_cap"]))
    
    with col4:
        if "pe_ratio" in data:
            st.metric("PE", f"{data['pe_ratio']:.1f}" if data["pe_ratio"] else "N/A")


def render_market_indices(indices: List[Dict[str, Any]]) -> None:
    """渲染市场指数"""
    cols = st.columns(len(indices))
    
    for col, idx in zip(cols, indices):
        with col:
            price = idx.get("price", idx.get("last_price"))
            change = idx.get("change_percent", idx.get("change_pct", 0))
            
            st.metric(
                label=idx.get("name", idx.get("code", "N/A")),
                value=f"{price:.2f}" if price else "N/A",
                delta=f"{change:.2f}%" if change else None,
            )


def render_financial_table(df: pd.DataFrame, title: str = "") -> None:
    """渲染财务数据表格"""
    if title:
        st.subheader(title)
    
    if df.empty or "error" in df.columns:
        st.warning("暂无数据")
        return
    
    numeric_cols = df.select_dtypes(include=["number"]).columns
    formatted_df = df.copy()
    
    for col in numeric_cols:
        formatted_df[col] = formatted_df[col].apply(
            lambda x: format_number(x) if pd.notna(x) else "-"
        )
    
    st.dataframe(formatted_df, use_container_width=True)


def render_analysis_result(result: Dict[str, Any]) -> None:
    """渲染分析结果"""
    if "recommendation" in result:
        st.markdown("### 投资建议")
        st.markdown(result["recommendation"])
    
    if "confidence" in result:
        confidence = result["confidence"]
        st.progress(confidence, text=f"置信度: {confidence * 100:.0f}%")
    
    if "errors" in result and result["errors"]:
        with st.expander("⚠️ 分析过程中的问题"):
            for error in result["errors"]:
                st.error(error)
    
    if "messages" in result:
        with st.expander("📊 详细分析过程"):
            for msg in result["messages"]:
                role = msg.get("role", "agent")
                content = msg.get("content", "")
                st.markdown(f"**{role}**")
                st.markdown(content)
                st.divider()


def render_search_results(results: List[Dict[str, Any]]) -> None:
    """渲染搜索结果"""
    if not results:
        st.info("未找到相关内容")
        return
    
    for i, result in enumerate(results):
        score = result.get("score", 0)
        metadata = result.get("metadata", {})
        text = result.get("text", "")
        
        with st.expander(
            f"📄 {metadata.get('report_title', '未知报告')} (相关度: {score:.2f})",
            expanded=i == 0
        ):
            st.caption(f"股票: {metadata.get('stock_code', 'N/A')} | 年份: {metadata.get('report_year', 'N/A')}")
            st.markdown(text)


def render_report_list(reports: List[Dict[str, Any]]) -> None:
    """渲染报告列表"""
    if not reports:
        st.info("暂无已索引的财报")
        return
    
    df = pd.DataFrame(reports)
    st.dataframe(
        df,
        column_config={
            "stock_code": "股票代码",
            "report_title": "报告标题",
            "report_year": "年份",
            "chunk_count": "文档块数",
        },
        use_container_width=True,
    )


def stock_input() -> str:
    """股票代码输入组件"""
    return st.text_input(
        "股票代码",
        placeholder="例如: AAPL, sh600519, 000001",
        help="支持美股代码、A股代码（sh/sz前缀或6位数字）、港股代码（hk前缀）"
    )


def render_disclaimer() -> None:
    """渲染免责声明"""
    st.caption(
        "⚠️ **免责声明**: 本工具仅供研究和学习使用，"
        "分析结果不构成投资建议。投资有风险，决策需谨慎。"
    )


def format_number(value: float) -> str:
    """格式化数字"""
    if pd.isna(value):
        return "-"
    if abs(value) >= 1e12:
        return f"{value / 1e12:.2f}万亿"
    if abs(value) >= 1e8:
        return f"{value / 1e8:.2f}亿"
    if abs(value) >= 1e4:
        return f"{value / 1e4:.2f}万"
    return f"{value:,.2f}"
