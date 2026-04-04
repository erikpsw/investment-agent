from typing import Any
import pandas as pd
from .state import InvestmentState
from .llm import get_llm_client
from ..data import StockFetcher


fetcher = StockFetcher()


def analyze_technicals(state: InvestmentState) -> dict[str, Any]:
    """技术面分析节点
    
    分析内容：
    - 价格趋势
    - 技术指标（MA、RSI、MACD 等）
    - 支撑位和压力位
    - 成交量分析
    """
    ticker = state.get("ticker", "")
    market = state.get("market", "")
    
    if not ticker:
        return {"errors": ["缺少股票代码"]}
    
    if market == "CN":
        return {
            "technical_analysis": "A股技术分析需要历史数据接口支持",
            "errors": ["A股历史数据暂未实现"],
        }
    
    try:
        history = fetcher.get_history(ticker, period="6mo", interval="1d")
        
        if history.empty:
            return {"errors": ["获取历史数据失败"]}
        
        indicators = calculate_indicators(history)
        
        llm = get_llm_client()
        analysis = llm.analyze(
            data={
                "ticker": ticker,
                "current_price": history["Close"].iloc[-1],
                "indicators": indicators,
                "recent_high": history["High"].max(),
                "recent_low": history["Low"].min(),
                "avg_volume": history["Volume"].mean(),
            },
            task="对该股票进行技术面分析，评估趋势、动量和交易信号",
            format_hint="""请按以下格式输出：
## 趋势分析
...

## 技术指标
- RSI: ...
- MACD: ...
- 均线: ...

## 支撑/压力位
...

## 交易信号
..."""
        )
        
        return {
            "history_data": {
                "period": "6mo",
                "interval": "1d",
                "data_points": len(history),
            },
            "technical_analysis": analysis,
            "messages": [{
                "role": "technical_agent",
                "content": analysis,
            }],
        }
        
    except Exception as e:
        return {"errors": [f"技术面分析失败: {str(e)}"]}


def calculate_indicators(df: pd.DataFrame) -> dict[str, Any]:
    """计算技术指标"""
    close = df["Close"]
    
    ma5 = close.rolling(window=5).mean().iloc[-1]
    ma20 = close.rolling(window=20).mean().iloc[-1]
    ma60 = close.rolling(window=60).mean().iloc[-1] if len(close) >= 60 else None
    
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    
    ema12 = close.ewm(span=12).mean()
    ema26 = close.ewm(span=26).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9).mean()
    
    bb_middle = close.rolling(window=20).mean()
    bb_std = close.rolling(window=20).std()
    bb_upper = bb_middle + 2 * bb_std
    bb_lower = bb_middle - 2 * bb_std
    
    current_price = close.iloc[-1]
    
    return {
        "current_price": current_price,
        "ma5": ma5,
        "ma20": ma20,
        "ma60": ma60,
        "rsi_14": rsi.iloc[-1],
        "macd": macd.iloc[-1],
        "macd_signal": signal.iloc[-1],
        "macd_histogram": (macd - signal).iloc[-1],
        "bollinger_upper": bb_upper.iloc[-1],
        "bollinger_middle": bb_middle.iloc[-1],
        "bollinger_lower": bb_lower.iloc[-1],
        "price_vs_ma20": (current_price / ma20 - 1) * 100 if ma20 else None,
        "trend": "上升" if ma5 > ma20 else "下降",
    }


def get_price_data(state: InvestmentState) -> dict[str, Any]:
    """获取实时价格数据"""
    ticker = state.get("ticker", "")
    if not ticker:
        return {"errors": ["缺少股票代码"]}
    
    try:
        quote = fetcher.get_quote(ticker)
        
        if "error" in quote:
            return {"errors": [f"获取行情失败: {quote['error']}"]}
        
        return {
            "price_data": quote,
            "messages": [{
                "role": "data_agent",
                "content": f"当前价格: {quote.get('price', 'N/A')}",
            }],
        }
        
    except Exception as e:
        return {"errors": [f"获取价格数据失败: {str(e)}"]}
