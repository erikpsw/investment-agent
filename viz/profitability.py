import plotly.graph_objects as go
import pandas as pd
from typing import Any


def plot_profit_margins(
    df: pd.DataFrame,
    date_col: str = "报告期",
    gross_margin_col: str = "毛利率",
    net_margin_col: str = "净利率",
    roe_col: str = "ROE",
    title: str = "盈利能力分析",
) -> go.Figure:
    """绘制利润率分析图
    
    Args:
        df: 包含财务指标的 DataFrame
        date_col: 日期列名
        gross_margin_col: 毛利率列名
        net_margin_col: 净利率列名
        roe_col: ROE 列名
        title: 图表标题
        
    Returns:
        Plotly Figure 对象
    """
    df = df.sort_values(date_col)
    
    fig = go.Figure()
    
    if gross_margin_col in df.columns:
        fig.add_trace(go.Scatter(
            x=df[date_col],
            y=df[gross_margin_col] * 100 if df[gross_margin_col].max() <= 1 else df[gross_margin_col],
            name="毛利率",
            mode="lines+markers",
            line=dict(color="#3366CC", width=2),
            marker=dict(size=8),
        ))
    
    if net_margin_col in df.columns:
        fig.add_trace(go.Scatter(
            x=df[date_col],
            y=df[net_margin_col] * 100 if df[net_margin_col].max() <= 1 else df[net_margin_col],
            name="净利率",
            mode="lines+markers",
            line=dict(color="#DC3912", width=2),
            marker=dict(size=8),
        ))
    
    if roe_col in df.columns:
        fig.add_trace(go.Scatter(
            x=df[date_col],
            y=df[roe_col] * 100 if df[roe_col].max() <= 1 else df[roe_col],
            name="ROE",
            mode="lines+markers",
            line=dict(color="#FF9900", width=2),
            marker=dict(size=8),
        ))
    
    fig.update_layout(
        title=dict(text=title, font=dict(size=18)),
        xaxis=dict(title="报告期", tickangle=-45),
        yaxis=dict(title="百分比 (%)", ticksuffix="%"),
        legend=dict(x=0.01, y=0.99, bgcolor="rgba(255,255,255,0.8)"),
        hovermode="x unified",
        template="plotly_white",
    )
    
    return fig


def plot_profitability_radar(
    metrics: dict[str, float],
    industry_avg: dict[str, float] | None = None,
    title: str = "盈利能力雷达图",
) -> go.Figure:
    """绘制盈利能力雷达图
    
    Args:
        metrics: 公司指标 {"毛利率": 0.3, "净利率": 0.1, ...}
        industry_avg: 行业平均指标（可选）
        title: 图表标题
    """
    categories = list(metrics.keys())
    values = [v * 100 if v <= 1 else v for v in metrics.values()]
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatterpolar(
        r=values + [values[0]],
        theta=categories + [categories[0]],
        fill="toself",
        name="公司",
        line=dict(color="#3366CC"),
    ))
    
    if industry_avg:
        avg_values = [industry_avg.get(k, 0) * 100 if industry_avg.get(k, 0) <= 1 else industry_avg.get(k, 0) for k in categories]
        fig.add_trace(go.Scatterpolar(
            r=avg_values + [avg_values[0]],
            theta=categories + [categories[0]],
            fill="toself",
            name="行业平均",
            line=dict(color="#DC3912", dash="dash"),
            fillcolor="rgba(220, 57, 18, 0.1)",
        ))
    
    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                ticksuffix="%",
            )
        ),
        showlegend=True,
        title=dict(text=title, font=dict(size=18)),
    )
    
    return fig


def plot_cost_structure(
    df: pd.DataFrame,
    date_col: str = "报告期",
    columns: list[str] | None = None,
    title: str = "成本结构分析",
) -> go.Figure:
    """绘制成本结构堆叠图
    
    Args:
        df: 包含成本数据的 DataFrame
        date_col: 日期列名
        columns: 成本项列名列表
        title: 图表标题
    """
    if columns is None:
        columns = ["营业成本", "销售费用", "管理费用", "研发费用", "财务费用"]
        columns = [c for c in columns if c in df.columns]
    
    df = df.sort_values(date_col)
    
    fig = go.Figure()
    
    colors = ["#3366CC", "#DC3912", "#FF9900", "#109618", "#990099"]
    
    for i, col in enumerate(columns):
        if col in df.columns:
            fig.add_trace(go.Bar(
                x=df[date_col],
                y=df[col],
                name=col,
                marker_color=colors[i % len(colors)],
            ))
    
    fig.update_layout(
        barmode="stack",
        title=dict(text=title, font=dict(size=18)),
        xaxis=dict(title="报告期", tickangle=-45),
        yaxis=dict(title="金额", tickformat=".2s"),
        legend=dict(x=1.02, y=1),
        template="plotly_white",
    )
    
    return fig


def plot_margin_trend_area(
    df: pd.DataFrame,
    date_col: str = "报告期",
    revenue_col: str = "营业收入",
    cost_col: str = "营业成本",
    title: str = "收入成本对比",
) -> go.Figure:
    """绘制收入成本面积图
    
    Args:
        df: 财务数据 DataFrame
        date_col: 日期列名
        revenue_col: 收入列名
        cost_col: 成本列名
        title: 图表标题
    """
    df = df.sort_values(date_col)
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=df[date_col],
        y=df[revenue_col],
        name="营业收入",
        fill="tozeroy",
        mode="lines",
        line=dict(color="#3366CC"),
    ))
    
    if cost_col in df.columns:
        fig.add_trace(go.Scatter(
            x=df[date_col],
            y=df[cost_col],
            name="营业成本",
            fill="tozeroy",
            mode="lines",
            line=dict(color="#DC3912"),
        ))
    
    fig.update_layout(
        title=dict(text=title, font=dict(size=18)),
        xaxis=dict(title="报告期", tickangle=-45),
        yaxis=dict(title="金额", tickformat=".2s"),
        hovermode="x unified",
        template="plotly_white",
    )
    
    return fig
