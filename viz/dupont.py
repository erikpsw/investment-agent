import plotly.graph_objects as go
import pandas as pd
from typing import Any


def plot_dupont_analysis(
    data: dict[str, float] | pd.Series,
    title: str = "杜邦分析",
) -> go.Figure:
    """绘制杜邦分析树状图
    
    杜邦分析公式：
    ROE = 净利率 × 资产周转率 × 权益乘数
        = (净利润/营业收入) × (营业收入/总资产) × (总资产/股东权益)
    
    Args:
        data: 包含杜邦分析所需指标的字典或 Series
            必需: ROE, 净利率, 资产周转率, 权益乘数
            可选: 净利润, 营业收入, 总资产, 股东权益
        title: 图表标题
        
    Returns:
        Plotly Figure 对象
    """
    if isinstance(data, pd.Series):
        data = data.to_dict()
    
    roe = data.get("ROE", 0)
    net_margin = data.get("净利率", 0)
    asset_turnover = data.get("资产周转率", 0)
    equity_multiplier = data.get("权益乘数", 0)
    
    net_income = data.get("净利润", 0)
    revenue = data.get("营业收入", 0)
    total_assets = data.get("总资产", 0)
    equity = data.get("股东权益", 0)
    
    labels = [
        f"ROE<br>{format_percent(roe)}",
        f"净利率<br>{format_percent(net_margin)}",
        f"资产周转率<br>{format_ratio(asset_turnover)}",
        f"权益乘数<br>{format_ratio(equity_multiplier)}",
    ]
    
    parents = ["", "ROE", "ROE", "ROE"]
    values = [abs(roe), abs(net_margin), abs(asset_turnover), abs(equity_multiplier)]
    
    if net_income and revenue:
        labels.extend([
            f"净利润<br>{format_amount(net_income)}",
            f"营业收入<br>{format_amount(revenue)}",
        ])
        parents.extend([f"净利率<br>{format_percent(net_margin)}"] * 2)
        values.extend([abs(net_income), abs(revenue)])
    
    if revenue and total_assets:
        labels.extend([
            f"营业收入<br>{format_amount(revenue)}",
            f"总资产<br>{format_amount(total_assets)}",
        ])
        parents.extend([f"资产周转率<br>{format_ratio(asset_turnover)}"] * 2)
        values.extend([abs(revenue), abs(total_assets)])
    
    if total_assets and equity:
        labels.extend([
            f"总资产<br>{format_amount(total_assets)}",
            f"股东权益<br>{format_amount(equity)}",
        ])
        parents.extend([f"权益乘数<br>{format_ratio(equity_multiplier)}"] * 2)
        values.extend([abs(total_assets), abs(equity)])
    
    labels[0] = labels[0].replace("<br>", "<br><b>").replace(format_percent(roe), f"{format_percent(roe)}</b>")
    
    fig = go.Figure(go.Treemap(
        labels=labels[:4],
        parents=parents[:4],
        values=[1, 1, 1, 1],
        textinfo="label",
        marker=dict(
            colors=["#3366CC", "#109618", "#FF9900", "#DC3912"],
            line=dict(width=2, color="white"),
        ),
        textfont=dict(size=14),
    ))
    
    fig.update_layout(
        title=dict(text=title, font=dict(size=18)),
        margin=dict(t=50, l=25, r=25, b=25),
    )
    
    return fig


def plot_dupont_waterfall(
    data: dict[str, float] | pd.Series,
    title: str = "杜邦分析分解",
) -> go.Figure:
    """绘制杜邦分析瀑布图
    
    展示 ROE 的三因素分解过程
    """
    if isinstance(data, pd.Series):
        data = data.to_dict()
    
    net_margin = data.get("净利率", 0)
    asset_turnover = data.get("资产周转率", 0)
    equity_multiplier = data.get("权益乘数", 0)
    roe = net_margin * asset_turnover * equity_multiplier
    
    fig = go.Figure(go.Waterfall(
        x=["净利率", "× 资产周转率", "× 权益乘数", "= ROE"],
        y=[
            net_margin * 100,
            (net_margin * asset_turnover - net_margin) * 100,
            (roe - net_margin * asset_turnover) * 100,
            0
        ],
        measure=["absolute", "relative", "relative", "total"],
        text=[
            f"{net_margin * 100:.1f}%",
            f"{asset_turnover:.2f}×",
            f"{equity_multiplier:.2f}×",
            f"{roe * 100:.1f}%"
        ],
        textposition="outside",
        connector=dict(line=dict(color="rgb(63, 63, 63)")),
        decreasing=dict(marker=dict(color="#E74C3C")),
        increasing=dict(marker=dict(color="#2ECC71")),
        totals=dict(marker=dict(color="#3498DB")),
    ))
    
    fig.update_layout(
        title=dict(text=title, font=dict(size=18)),
        yaxis=dict(title="百分比 (%)", ticksuffix="%"),
        template="plotly_white",
    )
    
    return fig


def plot_dupont_comparison(
    current: dict[str, float],
    previous: dict[str, float],
    labels: tuple[str, str] = ("本期", "上期"),
    title: str = "杜邦分析对比",
) -> go.Figure:
    """绘制杜邦分析对比图
    
    Args:
        current: 本期数据
        previous: 上期数据
        labels: 标签 (本期名, 上期名)
        title: 图表标题
    """
    categories = ["ROE", "净利率", "资产周转率", "权益乘数"]
    
    current_values = [
        current.get("ROE", 0) * 100,
        current.get("净利率", 0) * 100,
        current.get("资产周转率", 0),
        current.get("权益乘数", 0),
    ]
    
    previous_values = [
        previous.get("ROE", 0) * 100,
        previous.get("净利率", 0) * 100,
        previous.get("资产周转率", 0),
        previous.get("权益乘数", 0),
    ]
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=categories,
        y=current_values,
        name=labels[0],
        marker_color="#3366CC",
        text=[f"{v:.1f}" for v in current_values],
        textposition="outside",
    ))
    
    fig.add_trace(go.Bar(
        x=categories,
        y=previous_values,
        name=labels[1],
        marker_color="#DC3912",
        text=[f"{v:.1f}" for v in previous_values],
        textposition="outside",
    ))
    
    fig.update_layout(
        title=dict(text=title, font=dict(size=18)),
        barmode="group",
        template="plotly_white",
    )
    
    return fig


def format_percent(value: float) -> str:
    """格式化百分比"""
    if value is None or pd.isna(value):
        return "N/A"
    if abs(value) <= 1:
        return f"{value * 100:.1f}%"
    return f"{value:.1f}%"


def format_ratio(value: float) -> str:
    """格式化比率"""
    if value is None or pd.isna(value):
        return "N/A"
    return f"{value:.2f}×"


def format_amount(value: float) -> str:
    """格式化金额"""
    if value is None or pd.isna(value):
        return "N/A"
    if abs(value) >= 1e8:
        return f"{value / 1e8:.1f}亿"
    elif abs(value) >= 1e4:
        return f"{value / 1e4:.1f}万"
    return f"{value:.0f}"
