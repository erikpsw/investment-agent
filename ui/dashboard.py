import streamlit as st
import plotly.graph_objects as go
from investment.data import StockFetcher
from investment.ui.components import render_market_indices, render_stock_card, render_disclaimer


def render_price_chart(fetcher: StockFetcher, ticker: str, name: str):
    """渲染价格走势图"""
    period_options = {"近1周": "5d", "近1月": "1mo", "近3月": "3mo", "近半年": "6mo", "近1年": "1y"}
    
    col1, col2 = st.columns([3, 1])
    with col2:
        selected_period = st.selectbox("周期", list(period_options.keys()), index=1, key="price_period")
    
    period = period_options[selected_period]
    
    try:
        history = fetcher.get_history(ticker, period=period, interval="1d")
        
        if history is None or history.empty:
            st.info("暂无历史数据")
            return
        
        fig = go.Figure()
        
        fig.add_trace(go.Candlestick(
            x=history.index,
            open=history["open"],
            high=history["high"],
            low=history["low"],
            close=history["close"],
            name="K线",
            increasing_line_color="#ef5350",
            decreasing_line_color="#26a69a",
        ))
        
        if len(history) >= 5:
            ma5 = history["close"].rolling(window=5).mean()
            fig.add_trace(go.Scatter(
                x=history.index,
                y=ma5,
                mode="lines",
                name="MA5",
                line=dict(color="#ffa726", width=1),
            ))
        
        if len(history) >= 20:
            ma20 = history["close"].rolling(window=20).mean()
            fig.add_trace(go.Scatter(
                x=history.index,
                y=ma20,
                mode="lines",
                name="MA20",
                line=dict(color="#42a5f5", width=1),
            ))
        
        fig.update_layout(
            title=dict(text=f"{name} 价格走势", font=dict(size=16)),
            xaxis=dict(
                title="日期",
                rangeslider=dict(visible=False),
                type="category",
            ),
            yaxis=dict(title="价格"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            height=400,
            template="plotly_white",
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        with st.expander("成交量"):
            vol_fig = go.Figure()
            colors = ["#ef5350" if c >= o else "#26a69a" for c, o in zip(history["close"], history["open"])]
            vol_fig.add_trace(go.Bar(
                x=history.index,
                y=history["volume"],
                marker_color=colors,
                name="成交量",
            ))
            vol_fig.update_layout(
                xaxis=dict(title="日期", type="category"),
                yaxis=dict(title="成交量"),
                height=200,
                template="plotly_white",
                showlegend=False,
            )
            st.plotly_chart(vol_fig, use_container_width=True)
            
    except Exception as e:
        st.warning(f"获取历史数据失败: {e}")


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
    
    st.caption("💡 支持输入公司名称（如：茅台、苹果、腾讯）或股票代码")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        user_input = st.text_input(
            "股票名称或代码",
            placeholder="输入公司名称或代码，如：茅台、苹果、AAPL、腾讯",
            key="dashboard_ticker"
        )
    
    with col2:
        st.write("")
        st.write("")
        search_clicked = st.button("查询", type="primary", use_container_width=True)
    
    if user_input and len(user_input) >= 2:
        try:
            search_results = fetcher.search(user_input, limit=5)
            if search_results:
                st.caption("🔍 匹配结果：")
                cols = st.columns(min(len(search_results), 5))
                for i, result in enumerate(search_results[:5]):
                    with cols[i]:
                        market_flag = {"CN": "🇨🇳", "HK": "🇭🇰", "US": "🇺🇸"}.get(result["market"], "")
                        if st.button(
                            f"{market_flag} {result['name'][:6]}",
                            key=f"quick_{i}",
                            help=result["display"],
                            use_container_width=True
                        ):
                            st.session_state["selected_stock"] = result
                            st.rerun()
        except Exception:
            pass
    
    selected = st.session_state.get("selected_stock")
    ticker_to_query = None
    
    if selected:
        ticker_to_query = selected.get("code")
        st.info(f"已选择: {selected.get('display', ticker_to_query)}")
        if st.button("清除选择", type="secondary"):
            del st.session_state["selected_stock"]
            st.rerun()
    elif search_clicked and user_input:
        resolved = fetcher.resolve_input(user_input)
        ticker_to_query = resolved.get("code")
    
    if ticker_to_query:
        with st.spinner("查询中..."):
            try:
                quote = fetcher.get_quote(ticker_to_query)
                
                if "error" in quote:
                    st.error(f"查询失败: {quote['error']}")
                else:
                    display_name = quote.get("name") or (selected.get("name") if selected else ticker_to_query)
                    st.subheader(f"{display_name} ({ticker_to_query})")
                    render_stock_card(quote)
                    
                    render_price_chart(fetcher, ticker_to_query, display_name)
                    
                    with st.expander("详细数据"):
                        st.json(quote)
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("📊 完整分析", use_container_width=True):
                            st.session_state["analysis_ticker"] = ticker_to_query
                    with col2:
                        if st.button("📈 财务图表", use_container_width=True):
                            st.session_state["chart_ticker"] = ticker_to_query
                            
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
