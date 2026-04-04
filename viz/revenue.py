import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from typing import Any


def plot_revenue_trend(
    df: pd.DataFrame,
    revenue_col: str = "营业收入",
    profit_col: str = "净利润",
    date_col: str = "报告期",
    title: str = "营业收入与净利润趋势",
) -> go.Figure:
    """绘制收入趋势图（柱状图 + 折线图组合）
    
    Args:
        df: 包含财务数据的 DataFrame
        revenue_col: 营业收入列名
        profit_col: 净利润列名
        date_col: 日期列名
        title: 图表标题
        
    Returns:
        Plotly Figure 对象
    """
    df = df.sort_values(date_col)
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=df[date_col],
        y=df[revenue_col],
        name="营业收入",
        marker_color="#3366CC",
        text=df[revenue_col].apply(lambda x: format_number(x)),
        textposition="outside",
    ))
    
    fig.add_trace(go.Scatter(
        x=df[date_col],
        y=df[profit_col],
        name="净利润",
        mode="lines+markers+text",
        line=dict(color="#DC3912", width=3),
        marker=dict(size=10),
        text=df[profit_col].apply(lambda x: format_number(x)),
        textposition="top center",
        yaxis="y2",
    ))
    
    fig.update_layout(
        title=dict(text=title, font=dict(size=18)),
        xaxis=dict(title="报告期", tickangle=-45),
        yaxis=dict(
            title=dict(text="营业收入", font=dict(color="#3366CC")),
            tickfont=dict(color="#3366CC"),
            tickformat=".2s",
        ),
        yaxis2=dict(
            title=dict(text="净利润", font=dict(color="#DC3912")),
            tickfont=dict(color="#DC3912"),
            anchor="x",
            overlaying="y",
            side="right",
            tickformat=".2s",
        ),
        legend=dict(x=0.01, y=0.99, bgcolor="rgba(255,255,255,0.8)"),
        hovermode="x unified",
        template="plotly_white",
    )
    
    return fig


def plot_revenue_growth(
    df: pd.DataFrame,
    revenue_col: str = "营业收入",
    date_col: str = "报告期",
    title: str = "营业收入同比增长率",
) -> go.Figure:
    """绘制收入增长率图
    
    Args:
        df: 包含财务数据的 DataFrame
        revenue_col: 营业收入列名
        date_col: 日期列名
        title: 图表标题
        
    Returns:
        Plotly Figure 对象
    """
    df = df.sort_values(date_col).copy()
    df["增长率"] = df[revenue_col].pct_change() * 100
    
    colors = ["#2ECC71" if x >= 0 else "#E74C3C" for x in df["增长率"].fillna(0)]
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=df[date_col],
        y=df["增长率"],
        marker_color=colors,
        text=df["增长率"].apply(lambda x: f"{x:.1f}%" if pd.notna(x) else ""),
        textposition="outside",
    ))
    
    fig.add_hline(y=0, line_dash="dash", line_color="gray")
    
    fig.update_layout(
        title=dict(text=title, font=dict(size=18)),
        xaxis=dict(title="报告期", tickangle=-45),
        yaxis=dict(title="同比增长率 (%)", ticksuffix="%"),
        template="plotly_white",
    )
    
    return fig


def plot_quarterly_comparison(
    df: pd.DataFrame,
    value_col: str = "营业收入",
    year_col: str = "年份",
    quarter_col: str = "季度",
    title: str = "季度营收对比",
) -> go.Figure:
    """绘制季度对比图
    
    Args:
        df: 包含年份和季度列的 DataFrame
        value_col: 数值列名
        year_col: 年份列名
        quarter_col: 季度列名
        title: 图表标题
    """
    fig = px.bar(
        df,
        x=quarter_col,
        y=value_col,
        color=year_col,
        barmode="group",
        title=title,
        text_auto=".2s",
    )
    
    fig.update_layout(
        xaxis_title="季度",
        yaxis_title=value_col,
        template="plotly_white",
    )
    
    return fig


def format_number(value: float) -> str:
    """格式化数字（亿/万）"""
    if pd.isna(value):
        return ""
    if abs(value) >= 1e8:
        return f"{value / 1e8:.1f}亿"
    elif abs(value) >= 1e4:
        return f"{value / 1e4:.1f}万"
    else:
        return f"{value:.0f}"
