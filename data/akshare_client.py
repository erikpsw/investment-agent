import akshare as ak
import pandas as pd
from typing import Any
from datetime import datetime


class AKShareClient:
    """A股财务数据客户端，基于 AKShare"""

    def get_balance_sheet(self, stock_code: str) -> pd.DataFrame:
        """获取资产负债表
        
        Args:
            stock_code: 股票代码，如 sh600519 或 600519
        """
        code = self._normalize_code(stock_code)
        try:
            return ak.stock_financial_report_sina(stock=code, symbol="资产负债表")
        except Exception as e:
            return pd.DataFrame({"error": [str(e)]})

    def get_income_statement(self, stock_code: str) -> pd.DataFrame:
        """获取利润表"""
        code = self._normalize_code(stock_code)
        try:
            return ak.stock_financial_report_sina(stock=code, symbol="利润表")
        except Exception as e:
            return pd.DataFrame({"error": [str(e)]})

    def get_cash_flow(self, stock_code: str) -> pd.DataFrame:
        """获取现金流量表"""
        code = self._normalize_code(stock_code)
        try:
            return ak.stock_financial_report_sina(stock=code, symbol="现金流量表")
        except Exception as e:
            return pd.DataFrame({"error": [str(e)]})

    def get_financial_summary(self, stock_code: str) -> dict[str, pd.DataFrame]:
        """获取完整财务报表"""
        return {
            "balance_sheet": self.get_balance_sheet(stock_code),
            "income_statement": self.get_income_statement(stock_code),
            "cash_flow": self.get_cash_flow(stock_code),
        }

    def get_stock_info(self, stock_code: str) -> dict[str, Any]:
        """获取股票基本信息"""
        code = stock_code.replace("sh", "").replace("sz", "")
        try:
            df = ak.stock_individual_info_em(symbol=code)
            info = {}
            for _, row in df.iterrows():
                info[row["item"]] = row["value"]
            return info
        except Exception as e:
            return {"error": str(e)}

    def get_financial_indicators(self, stock_code: str) -> pd.DataFrame:
        """获取主要财务指标
        
        使用同花顺财务摘要数据，包含 ROE、毛利率、净利率、资产负债率等
        """
        code = stock_code.replace("sh", "").replace("sz", "")
        try:
            df = ak.stock_financial_abstract_ths(symbol=code)
            if df.empty:
                return pd.DataFrame({"error": ["No data available"]})
            
            latest = df.iloc[-1].to_dict()
            
            def parse_percent(val):
                if val is None or val == "False" or val == False:
                    return None
                if isinstance(val, str):
                    return float(val.replace("%", "").replace(",", "")) / 100
                return float(val)
            
            def parse_number(val):
                if val is None or val == "False" or val == False:
                    return None
                if isinstance(val, str):
                    val = val.replace(",", "").replace("万", "")
                    try:
                        return float(val)
                    except:
                        return None
                return float(val)
            
            return pd.DataFrame([{
                "report_date": latest.get("报告期"),
                "roe": parse_percent(latest.get("净资产收益率")),
                "gross_margin": parse_percent(latest.get("销售毛利率")),
                "profit_margin": parse_percent(latest.get("销售净利率")),
                "debt_ratio": parse_percent(latest.get("资产负债率")),
                "current_ratio": parse_number(latest.get("流动比率")),
                "quick_ratio": parse_number(latest.get("速动比率")),
                "eps": parse_number(latest.get("基本每股收益")),
                "bvps": parse_number(latest.get("每股净资产")),
                "revenue_yoy": parse_percent(latest.get("营业总收入同比增长率")),
                "profit_yoy": parse_percent(latest.get("净利润同比增长率")),
            }])
        except Exception as e:
            return pd.DataFrame({"error": [str(e)]})

    def get_profit_forecast(self, stock_code: str) -> pd.DataFrame:
        """获取盈利预测"""
        code = stock_code.replace("sh", "").replace("sz", "")
        try:
            return ak.stock_profit_forecast_em(symbol=code)
        except Exception as e:
            return pd.DataFrame({"error": [str(e)]})

    def get_macro_data(self, indicator: str = "cpi") -> pd.DataFrame:
        """获取宏观经济数据
        
        Args:
            indicator: 指标类型 (cpi, ppi, gdp, pmi)
        """
        try:
            if indicator == "cpi":
                return ak.macro_china_cpi_yearly()
            elif indicator == "ppi":
                return ak.macro_china_ppi_yearly()
            elif indicator == "gdp":
                return ak.macro_china_gdp_yearly()
            elif indicator == "pmi":
                return ak.macro_china_pmi_yearly()
            else:
                return pd.DataFrame({"error": [f"未知指标: {indicator}"]})
        except Exception as e:
            return pd.DataFrame({"error": [str(e)]})

    def search_stock(self, keyword: str) -> pd.DataFrame:
        """搜索股票"""
        try:
            df = ak.stock_zh_a_spot_em()
            mask = (
                df["名称"].str.contains(keyword, na=False) |
                df["代码"].str.contains(keyword, na=False)
            )
            return df[mask][["代码", "名称", "最新价", "涨跌幅"]].head(20)
        except Exception as e:
            return pd.DataFrame({"error": [str(e)]})

    def get_industry_stocks(self, industry: str) -> pd.DataFrame:
        """获取行业成分股"""
        try:
            return ak.stock_board_industry_cons_em(symbol=industry)
        except Exception as e:
            return pd.DataFrame({"error": [str(e)]})

    def _normalize_code(self, code: str) -> str:
        """标准化股票代码为 AKShare 格式"""
        code = code.lower()
        if code.startswith("sh") or code.startswith("sz"):
            return code
        if code.startswith("6"):
            return f"sh{code}"
        else:
            return f"sz{code}"
