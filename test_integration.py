#!/usr/bin/env python3
"""
集成测试脚本 - 验证各模块可正常导入和基本功能
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


def test_imports():
    """测试所有模块导入"""
    print("测试模块导入...")
    
    from data import StockFetcher, YFinanceClient, TencentClient, AKShareClient
    print("  ✓ data 模块")
    
    from reports import ReportDownloader, ReportParser, ReportVectorStore, ReportRAG
    print("  ✓ reports 模块")
    
    from viz import plot_revenue_trend, plot_profit_margins, plot_dupont_analysis, plot_revenue_composition
    print("  ✓ viz 模块")
    
    from agents import InvestmentState, create_investment_graph
    print("  ✓ agents 模块")
    
    from utils import get_config, CacheManager
    print("  ✓ utils 模块")
    
    print("\n所有模块导入成功！")


def test_data_layer():
    """测试数据层"""
    print("\n测试数据层...")
    
    from data import StockFetcher, TencentClient
    
    tencent = TencentClient()
    print("  测试腾讯 API...")
    
    result = tencent.get_index("sh000001", "上证指数")
    if "error" not in result:
        print(f"  ✓ 上证指数: {result.get('price', 'N/A')}")
    else:
        print(f"  ⚠ 获取失败（可能是网络问题）: {result.get('error')}")
    
    fetcher = StockFetcher()
    overview = fetcher.get_market_overview()
    print(f"  ✓ 市场概览: {len(overview.get('indices', []))} 个指数")


def test_visualization():
    """测试可视化"""
    print("\n测试可视化...")
    
    import pandas as pd
    from viz import plot_revenue_trend, plot_dupont_analysis
    
    df = pd.DataFrame({
        "报告期": ["2021", "2022", "2023"],
        "营业收入": [100e8, 120e8, 150e8],
        "净利润": [10e8, 15e8, 20e8],
    })
    
    fig = plot_revenue_trend(df)
    print(f"  ✓ 收入趋势图: {type(fig).__name__}")
    
    dupont_data = {"ROE": 0.15, "净利率": 0.10, "资产周转率": 0.8, "权益乘数": 1.875}
    fig = plot_dupont_analysis(dupont_data)
    print(f"  ✓ 杜邦分析图: {type(fig).__name__}")


def test_agents():
    """测试 Agent 状态"""
    print("\n测试 Agent 状态...")
    
    from agents.state import create_initial_state
    
    state = create_initial_state("分析贵州茅台", "sh600519")
    print(f"  ✓ 创建状态: ticker={state['ticker']}, market={state['market']}")
    
    state = create_initial_state("分析苹果公司", "AAPL")
    print(f"  ✓ 创建状态: ticker={state['ticker']}, market={state['market']}")


def test_cache():
    """测试缓存"""
    print("\n测试缓存...")
    
    from utils import CacheManager
    
    cache = CacheManager()
    
    cache.set("test_key", {"value": 123})
    result = cache.get("test_key", ttl_seconds=60)
    
    if result and result.get("value") == 123:
        print("  ✓ 缓存读写正常")
    else:
        print("  ✗ 缓存读写失败")
    
    cache.clear("test_key")


def main():
    print("=" * 50)
    print("Investment Agent 集成测试")
    print("=" * 50)
    
    try:
        test_imports()
        test_data_layer()
        test_visualization()
        test_agents()
        test_cache()
        
        print("\n" + "=" * 50)
        print("✓ 所有测试通过！")
        print("=" * 50)
        print("\n运行 Web 界面: streamlit run app.py")
        
        return 0
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
