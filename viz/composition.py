import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from typing import Any


def plot_revenue_composition(
    df: pd.DataFrame,
    value_col: str = "金额",
    name_col: str = "业务板块",
    title: str = "收入构成",
) -> go.Figure:
    """绘制收入构成饼图（环形图）
    
    Args:
        df: 包含业务板块和金额的 DataFrame
        value_col: 金额列名
        name_col: 业务板块列名
        title: 图表标题
        
    Returns:
        Plotly Figure 对象
    """
    df = df.copy()
    total = df[value_col].sum()
    df["占比"] = df[value_col] / total * 100
    
    fig = px.pie(
        df,
        values=value_col,
        names=name_col,
        title=title,
        hole=0.4,
    )
    
    fig.update_traces(
        textposition="inside",
        textinfo="percent+label",
        hovertemplate="<b>%{label}</b><br>金额: %{value:,.0f}<br>占比: %{percent}<extra></extra>",
    )
    
    fig.update_layout(
        showlegend=True,
        legend=dict(
            orientation="v",
            yanchor="middle",
            y=0.5,
            xanchor="left",
            x=1.02,
        ),
        annotations=[dict(
            text=f"总计<br>{format_amount(total)}",
            x=0.5, y=0.5,
            font_size=14,
            showarrow=False,
        )],
    )
    
    return fig


def plot_revenue_composition_trend(
    df: pd.DataFrame,
    value_col: str = "金额",
    name_col: str = "业务板块",
    date_col: str = "报告期",
    title: str = "收入构成变化趋势",
) -> go.Figure:
    """绘制收入构成变化趋势（堆叠面积图）
    
    Args:
        df: 包含多期数据的 DataFrame
        value_col: 金额列名
        name_col: 业务板块列名
        date_col: 日期列名
        title: 图表标题
    """
    pivot_df = df.pivot_table(
        index=date_col,
        columns=name_col,
        values=value_col,
        aggfunc="sum",
    ).fillna(0)
    
    fig = go.Figure()
    
    colors = px.colors.qualitative.Set2
    
    for i, col in enumerate(pivot_df.columns):
        fig.add_trace(go.Scatter(
            x=pivot_df.index,
            y=pivot_df[col],
            name=col,
            mode="lines",
            stackgroup="one",
            line=dict(width=0.5),
            fillcolor=colors[i % len(colors)],
        ))
    
    fig.update_layout(
        title=dict(text=title, font=dict(size=18)),
        xaxis=dict(title="报告期", tickangle=-45),
        yaxis=dict(title="金额", tickformat=".2s"),
        hovermode="x unified",
        template="plotly_white",
    )
    
    return fig


def plot_revenue_composition_bar(
    df: pd.DataFrame,
    value_col: str = "金额",
    name_col: str = "业务板块",
    date_col: str = "报告期",
    title: str = "收入构成对比",
) -> go.Figure:
    """绘制收入构成堆叠柱状图
    
    Args:
        df: 包含多期数据的 DataFrame
        value_col: 金额列名
        name_col: 业务板块列名
        date_col: 日期列名
        title: 图表标题
    """
    fig = px.bar(
        df,
        x=date_col,
        y=value_col,
        color=name_col,
        title=title,
        barmode="stack",
    )
    
    fig.update_layout(
        xaxis=dict(title="报告期", tickangle=-45),
        yaxis=dict(title="金额", tickformat=".2s"),
        legend=dict(
            title="业务板块",
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
        ),
        template="plotly_white",
    )
    
    return fig


def plot_cost_composition(
    df: pd.DataFrame,
    value_col: str = "金额",
    name_col: str = "成本项目",
    title: str = "成本构成",
) -> go.Figure:
    """绘制成本构成饼图
    
    Args:
        df: 包含成本项目和金额的 DataFrame
        value_col: 金额列名
        name_col: 成本项目列名
        title: 图表标题
    """
    fig = px.pie(
        df,
        values=value_col,
        names=name_col,
        title=title,
        hole=0.3,
        color_discrete_sequence=px.colors.sequential.RdBu,
    )
    
    fig.update_traces(
        textposition="outside",
        textinfo="percent+label",
    )
    
    return fig


def plot_asset_composition(
    assets: dict[str, float],
    title: str = "资产构成",
) -> go.Figure:
    """绘制资产构成旭日图
    
    Args:
        assets: 资产字典 {"流动资产": {"现金": 100, "应收账款": 50}, ...}
        title: 图表标题
    """
    labels = []
    parents = []
    values = []
    
    for category, items in assets.items():
        if isinstance(items, dict):
            labels.append(category)
            parents.append("")
            values.append(sum(items.values()))
            
            for name, value in items.items():
                labels.append(name)
                parents.append(category)
                values.append(value)
        else:
            labels.append(category)
            parents.append("")
            values.append(items)
    
    fig = go.Figure(go.Sunburst(
        labels=labels,
        parents=parents,
        values=values,
        branchvalues="total",
    ))
    
    fig.update_layout(
        title=dict(text=title, font=dict(size=18)),
        margin=dict(t=50, l=25, r=25, b=25),
    )
    
    return fig


def format_amount(value: float) -> str:
    """格式化金额"""
    if pd.isna(value):
        return ""
    if abs(value) >= 1e8:
        return f"{value / 1e8:.1f}亿"
    elif abs(value) >= 1e4:
        return f"{value / 1e4:.1f}万"
    return f"{value:,.0f}"
