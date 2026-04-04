import streamlit as st
from ..data import StockFetcher
from .components import render_market_indices, render_stock_card, render_disclaimer


def render_dashboard():
    """渲染主仪表盘"""
    st.title("📈 投资分析仪表盘")
    
    fetcher = StockFetcher()
    
    st.header("市场概览")
    
    with st.spinner("加载市场数据..."):
        try:
            market = fetcher.get_market_overview()
            indices = market.get("indices", [])
            
            if indices:
                render_market_indices(indices)
            else:
                st.warning("无法获取市场数据")
        except Exception as e:
            st.error(f"获取市场数据失败: {e}")
    
    st.divider()
    
    st.header("快速查询")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        ticker = st.text_input(
            "股票代码",
            placeholder="输入股票代码，如 AAPL, sh600519, 000001",
            key="dashboard_ticker"
        )
    
    with col2:
        st.write("")
        st.write("")
        search_clicked = st.button("查询", type="primary", use_container_width=True)
    
    if search_clicked and ticker:
        with st.spinner("查询中..."):
            try:
                quote = fetcher.get_quote(ticker)
                
                if "error" in quote:
                    st.error(f"查询失败: {quote['error']}")
                else:
                    st.subheader(f"{quote.get('name', ticker)} ({ticker})")
                    render_stock_card(quote)
                    
                    with st.expander("详细数据"):
                        st.json(quote)
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("📊 完整分析", use_container_width=True):
                            st.session_state["analysis_ticker"] = ticker
                            st.switch_page("pages/stock_analysis.py")
                    with col2:
                        if st.button("📈 财务图表", use_container_width=True):
                            st.session_state["chart_ticker"] = ticker
                            st.switch_page("pages/financial_charts.py")
                            
            except Exception as e:
                st.error(f"查询失败: {e}")
    
    st.divider()
    
    st.header("功能导航")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        ### 📊 个股分析
        多维度投资分析
        - 基本面分析
        - 技术面分析
        - 风险评估
        """)
    
    with col2:
        st.markdown("""
        ### 📄 财报查看
        财报 PDF 管理
        - 下载财报
        - 解析内容
        - 语义搜索
        """)
    
    with col3:
        st.markdown("""
        ### 📈 可视化
        财务数据可视化
        - 收入趋势
        - 杜邦分析
        - 盈利能力
        """)
    
    st.divider()
    render_disclaimer()
