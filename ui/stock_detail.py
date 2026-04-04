import streamlit as st
from investment.data import StockFetcher
from investment.agents.graph import run_analysis, run_quick_analysis
from investment.ui.components import (
    render_stock_card,
    render_analysis_result,
    render_financial_table,
    render_disclaimer,
)


def render_stock_detail():
    """渲染个股分析页面"""
    st.title("📊 个股分析")
    
    fetcher = StockFetcher()
    
    saved_ticker = st.session_state.get("analysis_ticker", "")
    
    st.caption("💡 支持输入公司名称（如：茅台、苹果、腾讯）或股票代码")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        user_input = st.text_input(
            "股票名称或代码",
            value=saved_ticker,
            placeholder="输入公司名称或代码，如：茅台、苹果、AAPL",
            key="stock_detail_input"
        )
    
    with col2:
        st.write("")
        st.write("")
        analysis_type = st.selectbox(
            "分析类型",
            ["快速分析", "完整分析"],
            key="analysis_type"
        )
    
    if user_input and len(user_input) >= 2:
        try:
            search_results = fetcher.search(user_input, limit=5)
            if search_results:
                st.caption("🔍 匹配结果（点击选择）：")
                cols = st.columns(min(len(search_results), 5))
                for i, result in enumerate(search_results[:5]):
                    with cols[i]:
                        market_flag = {"CN": "🇨🇳", "HK": "🇭🇰", "US": "🇺🇸"}.get(result["market"], "")
                        if st.button(
                            f"{market_flag} {result['name'][:8]}",
                            key=f"search_{i}",
                            help=result["display"],
                            use_container_width=True
                        ):
                            st.session_state["detail_selected_stock"] = result
                            st.rerun()
        except Exception:
            pass
    
    selected = st.session_state.get("detail_selected_stock")
    ticker = None
    stock_name = None
    
    if selected:
        ticker = selected.get("code")
        stock_name = selected.get("name")
        st.success(f"✓ 已选择: {selected.get('display', ticker)}")
        if st.button("清除选择", type="secondary"):
            del st.session_state["detail_selected_stock"]
            st.rerun()
    elif user_input:
        resolved = fetcher.resolve_input(user_input)
        ticker = resolved.get("code")
        stock_name = resolved.get("name")
    
    if not ticker:
        st.info("请输入股票名称或代码开始分析")
        return
    
    col1, col2 = st.columns(2)
    
    with col1:
        analyze_clicked = st.button("🚀 开始分析", type="primary", use_container_width=True)
    
    with col2:
        refresh_clicked = st.button("🔄 刷新数据", use_container_width=True)
    
    if analyze_clicked or refresh_clicked:
        with st.spinner("获取实时行情..."):
            try:
                quote = fetcher.get_quote(ticker)
                if "error" not in quote:
                    display_name = quote.get("name") or stock_name or ticker
                    st.subheader(f"实时行情 - {display_name}")
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
