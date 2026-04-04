import streamlit as st
import pandas as pd
from ..data import StockFetcher, AKShareClient
from ..viz import (
    plot_revenue_trend,
    plot_profit_margins,
    plot_dupont_analysis,
    plot_revenue_composition,
)
from .components import render_disclaimer


def render_financial_charts():
    """渲染财务图表页面"""
    st.title("📈 财务可视化")
    
    ticker = st.session_state.get("chart_ticker", "")
    
    ticker = st.text_input(
        "股票代码",
        value=ticker,
        placeholder="输入股票代码，如 sh600519",
        key="chart_ticker_input"
    )
    
    if not ticker:
        st.info("请输入股票代码查看财务图表")
        render_demo_charts()
        return
    
    if st.button("📊 加载数据", type="primary"):
        render_stock_charts(ticker)
    
    st.divider()
    render_disclaimer()


def render_stock_charts(ticker: str):
    """渲染股票财务图表"""
    fetcher = StockFetcher()
    akshare = AKShareClient()
    
    with st.spinner("加载财务数据..."):
        try:
            key_metrics = fetcher.get_key_metrics(ticker)
            
            if "error" in key_metrics:
                st.error(f"获取数据失败: {key_metrics['error']}")
                return
            
        except Exception as e:
            st.error(f"获取数据失败: {e}")
            return
    
    tab1, tab2, tab3, tab4 = st.tabs(["收入趋势", "盈利能力", "杜邦分析", "收入构成"])
    
    with tab1:
        st.subheader("收入与利润趋势")
        
        try:
            income_df = akshare.get_income_statement(ticker)
            
            if "error" not in income_df.columns and len(income_df) > 0:
                if "报告日" in income_df.columns:
                    income_df = income_df.rename(columns={"报告日": "报告期"})
                
                revenue_cols = [c for c in income_df.columns if "营业收入" in c or "收入" in c]
                profit_cols = [c for c in income_df.columns if "净利润" in c]
                
                if revenue_cols and profit_cols:
                    chart_df = pd.DataFrame({
                        "报告期": income_df.iloc[:, 0].head(8),
                        "营业收入": pd.to_numeric(income_df[revenue_cols[0]].head(8), errors="coerce"),
                        "净利润": pd.to_numeric(income_df[profit_cols[0]].head(8), errors="coerce"),
                    })
                    
                    fig = plot_revenue_trend(chart_df)
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("数据格式不支持，显示示例图表")
                    render_demo_revenue_chart()
            else:
                st.info("无法获取利润表数据，显示示例图表")
                render_demo_revenue_chart()
                
        except Exception as e:
            st.warning(f"加载收入趋势失败: {e}")
            render_demo_revenue_chart()
    
    with tab2:
        st.subheader("盈利能力分析")
        
        margins = {
            "毛利率": key_metrics.get("gross_margin"),
            "净利率": key_metrics.get("profit_margin"),
            "ROE": key_metrics.get("roe"),
            "ROA": key_metrics.get("roa"),
        }
        
        valid_margins = {k: v for k, v in margins.items() if v is not None}
        
        if valid_margins:
            cols = st.columns(len(valid_margins))
            for col, (name, value) in zip(cols, valid_margins.items()):
                with col:
                    pct_value = value * 100 if value < 1 else value
                    st.metric(name, f"{pct_value:.1f}%")
        else:
            st.info("暂无盈利能力数据")
    
    with tab3:
        st.subheader("杜邦分析")
        
        roe = key_metrics.get("roe")
        profit_margin = key_metrics.get("profit_margin")
        
        if roe and profit_margin:
            dupont_data = {
                "ROE": roe,
                "净利率": profit_margin,
                "资产周转率": key_metrics.get("asset_turnover", 0.5),
                "权益乘数": key_metrics.get("equity_multiplier", 2.0),
            }
            
            fig = plot_dupont_analysis(dupont_data)
            st.plotly_chart(fig, use_container_width=True)
            
            st.markdown("""
            **杜邦分析公式**: ROE = 净利率 × 资产周转率 × 权益乘数
            
            - **净利率**: 衡量盈利能力
            - **资产周转率**: 衡量运营效率
            - **权益乘数**: 衡量财务杠杆
            """)
        else:
            st.info("数据不足，无法进行杜邦分析")
    
    with tab4:
        st.subheader("收入构成")
        st.info("收入构成数据需要从财报中解析，请在财报查看器中导入财报后查看")
        render_demo_composition_chart()


def render_demo_charts():
    """渲染示例图表"""
    st.markdown("### 示例图表")
    
    with st.expander("📊 收入趋势示例", expanded=True):
        render_demo_revenue_chart()
    
    with st.expander("📈 杜邦分析示例"):
        demo_dupont = {
            "ROE": 0.15,
            "净利率": 0.10,
            "资产周转率": 0.8,
            "权益乘数": 1.875,
        }
        fig = plot_dupont_analysis(demo_dupont)
        st.plotly_chart(fig, use_container_width=True)


def render_demo_revenue_chart():
    """渲染示例收入图表"""
    demo_df = pd.DataFrame({
        "报告期": ["2020", "2021", "2022", "2023"],
        "营业收入": [100e8, 120e8, 150e8, 180e8],
        "净利润": [10e8, 15e8, 20e8, 25e8],
    })
    fig = plot_revenue_trend(demo_df)
    st.plotly_chart(fig, use_container_width=True)


def render_demo_composition_chart():
    """渲染示例收入构成图表"""
    demo_df = pd.DataFrame({
        "业务板块": ["主营业务A", "主营业务B", "其他业务", "投资收益"],
        "金额": [60e8, 30e8, 8e8, 2e8],
    })
    fig = plot_revenue_composition(demo_df)
    st.plotly_chart(fig, use_container_width=True)
