import streamlit as st
from ..data import StockFetcher
from ..agents.graph import run_analysis, run_quick_analysis
from .components import (
    render_stock_card,
    render_analysis_result,
    render_financial_table,
    render_disclaimer,
)


def render_stock_detail():
    """渲染个股分析页面"""
    st.title("📊 个股分析")
    
    ticker = st.session_state.get("analysis_ticker", "")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        ticker = st.text_input(
            "股票代码",
            value=ticker,
            placeholder="输入股票代码，如 AAPL, sh600519",
            key="stock_detail_ticker"
        )
    
    with col2:
        st.write("")
        st.write("")
        analysis_type = st.selectbox(
            "分析类型",
            ["快速分析", "完整分析"],
            key="analysis_type"
        )
    
    if not ticker:
        st.info("请输入股票代码开始分析")
        return
    
    col1, col2 = st.columns(2)
    
    with col1:
        analyze_clicked = st.button("🚀 开始分析", type="primary", use_container_width=True)
    
    with col2:
        refresh_clicked = st.button("🔄 刷新数据", use_container_width=True)
    
    if analyze_clicked or refresh_clicked:
        fetcher = StockFetcher()
        
        with st.spinner("获取实时行情..."):
            try:
                quote = fetcher.get_quote(ticker)
                if "error" not in quote:
                    st.subheader("实时行情")
                    render_stock_card(quote)
                else:
                    st.warning(f"获取行情失败: {quote.get('error')}")
            except Exception as e:
                st.error(f"获取行情失败: {e}")
        
        st.divider()
        
        if analysis_type == "快速分析":
            with st.spinner("执行快速分析..."):
                try:
                    result = run_quick_analysis(ticker)
                    render_analysis_result(result)
                except Exception as e:
                    st.error(f"分析失败: {e}")
        else:
            with st.spinner("执行完整分析（可能需要较长时间）..."):
                try:
                    result = run_analysis(ticker)
                    render_analysis_result(result)
                except Exception as e:
                    st.error(f"分析失败: {e}")
        
        st.divider()
        
        with st.expander("📊 财务数据", expanded=False):
            with st.spinner("加载财务数据..."):
                try:
                    financials = fetcher.get_financials(ticker)
                    
                    if "income_statement" in financials:
                        render_financial_table(
                            financials["income_statement"],
                            "利润表"
                        )
                    
                    if "balance_sheet" in financials:
                        render_financial_table(
                            financials["balance_sheet"],
                            "资产负债表"
                        )
                        
                except Exception as e:
                    st.warning(f"获取财务数据失败: {e}")
    
    st.divider()
    render_disclaimer()
