"""
Ashare A股行情客户端 - 基于新浪/腾讯双数据源，完全免费无限流
原项目: https://github.com/mpquant/Ashare
"""
import json
import requests
import datetime
import pandas as pd
from typing import Any, Optional, Dict, List


class AshareQuoteClient:
    """A股实时行情客户端，新浪/腾讯双数据源自动切换"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        })
    
    def get_price(
        self,
        code: str,
        end_date: str = "",
        count: int = 10,
        frequency: str = "1d"
    ) -> pd.DataFrame:
        """获取股票行情数据
        
        Args:
            code: 股票代码，支持多种格式：
                - sh600519, sz000001
                - 600519.XSHG, 000001.XSHE
                - 600519, 000001
            end_date: 结束日期，格式 'YYYY-MM-DD'
            count: 获取数量
            frequency: 周期
                - '1d' 日线
                - '1w' 周线
                - '1M' 月线
                - '1m','5m','15m','30m','60m' 分钟线
                
        Returns:
            DataFrame with columns: open, close, high, low, volume
        """
        xcode = self._normalize_code(code)
        
        if frequency in ['1d', '1w', '1M']:
            try:
                return self._get_price_sina(xcode, end_date, count, frequency)
            except Exception:
                return self._get_price_day_tx(xcode, end_date, count, frequency)
        
        if frequency in ['1m', '5m', '15m', '30m', '60m']:
            if frequency == '1m':
                return self._get_price_min_tx(xcode, end_date, count, frequency)
            try:
                return self._get_price_sina(xcode, end_date, count, frequency)
            except Exception:
                return self._get_price_min_tx(xcode, end_date, count, frequency)
        
        return pd.DataFrame()
    
    def get_realtime_quote(self, code: str) -> Dict[str, Any]:
        """获取实时行情
        
        Args:
            code: 股票代码
            
        Returns:
            包含实时行情数据的字典
        """
        xcode = self._normalize_code(code)
        
        try:
            return self._get_realtime_sina(xcode)
        except Exception:
            try:
                return self._get_realtime_tx(xcode)
            except Exception as e:
                return {"error": str(e), "ticker": code}
    
    def get_realtime_quotes(self, codes: List[str]) -> List[Dict[str, Any]]:
        """批量获取实时行情
        
        Args:
            codes: 股票代码列表
            
        Returns:
            行情数据列表
        """
        results = []
        normalized = [self._normalize_code(c) for c in codes]
        
        try:
            quotes = self._get_batch_realtime_sina(normalized)
            return quotes
        except Exception:
            for code in codes:
                results.append(self.get_realtime_quote(code))
            return results
    
    def _normalize_code(self, code: str) -> str:
        """标准化股票代码"""
        code = code.strip()
        xcode = code.replace('.XSHG', '').replace('.XSHE', '')
        
        if 'XSHG' in code:
            return f'sh{xcode}'
        elif 'XSHE' in code:
            return f'sz{xcode}'
        elif code.lower().startswith(('sh', 'sz')):
            return code.lower()
        elif code.isdigit():
            if code.startswith('6'):
                return f'sh{code}'
            else:
                return f'sz{code}'
        
        return code
    
    def _get_price_day_tx(
        self,
        code: str,
        end_date: str = "",
        count: int = 10,
        frequency: str = "1d"
    ) -> pd.DataFrame:
        """腾讯日线数据"""
        unit = 'week' if frequency == '1w' else 'month' if frequency == '1M' else 'day'
        
        if end_date:
            if isinstance(end_date, datetime.date):
                end_date = end_date.strftime('%Y-%m-%d')
            else:
                end_date = end_date.split(' ')[0]
            if end_date == datetime.datetime.now().strftime('%Y-%m-%d'):
                end_date = ''
        
        url = f'http://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={code},{unit},,{end_date},{count},qfq'
        resp = self.session.get(url, timeout=10)
        st = json.loads(resp.content)
        
        ms = 'qfq' + unit
        stk = st['data'][code]
        buf = stk[ms] if ms in stk else stk[unit]
        
        df = pd.DataFrame(buf, columns=['time', 'open', 'close', 'high', 'low', 'volume'], dtype='float')
        df['time'] = pd.to_datetime(df['time'])
        df.set_index('time', inplace=True)
        df.index.name = ''
        
        return df
    
    def _get_price_min_tx(
        self,
        code: str,
        end_date: str = "",
        count: int = 10,
        frequency: str = "1m"
    ) -> pd.DataFrame:
        """腾讯分钟线数据"""
        ts = int(frequency[:-1]) if frequency[:-1].isdigit() else 1
        
        url = f'http://ifzq.gtimg.cn/appstock/app/kline/mkline?param={code},m{ts},,{count}'
        resp = self.session.get(url, timeout=10)
        st = json.loads(resp.content)
        
        buf = st['data'][code]['m' + str(ts)]
        df = pd.DataFrame(buf, columns=['time', 'open', 'close', 'high', 'low', 'volume', 'n1', 'n2'])
        df = df[['time', 'open', 'close', 'high', 'low', 'volume']]
        df[['open', 'close', 'high', 'low', 'volume']] = df[['open', 'close', 'high', 'low', 'volume']].astype('float')
        df['time'] = pd.to_datetime(df['time'])
        df.set_index('time', inplace=True)
        df.index.name = ''
        
        df['close'].iloc[-1] = float(st['data'][code]['qt'][code][3])
        
        return df
    
    def _get_price_sina(
        self,
        code: str,
        end_date: str = "",
        count: int = 10,
        frequency: str = "60m"
    ) -> pd.DataFrame:
        """新浪全周期数据"""
        freq_map = {'1d': '240m', '1w': '1200m', '1M': '7200m'}
        frequency = freq_map.get(frequency, frequency)
        mcount = count
        
        ts = int(frequency[:-1]) if frequency[:-1].isdigit() else 1
        
        if end_date and frequency in ['240m', '1200m', '7200m']:
            if not isinstance(end_date, datetime.date):
                end_date = pd.to_datetime(end_date)
            unit = 4 if frequency == '1200m' else 29 if frequency == '7200m' else 1
            count = count + (datetime.datetime.now() - end_date).days // unit
        
        url = f'http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={code}&scale={ts}&ma=5&datalen={count}'
        resp = self.session.get(url, timeout=10)
        dstr = json.loads(resp.content)
        
        df = pd.DataFrame(dstr, columns=['day', 'open', 'high', 'low', 'close', 'volume'])
        df['open'] = df['open'].astype(float)
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)
        df['close'] = df['close'].astype(float)
        df['volume'] = df['volume'].astype(float)
        df['day'] = pd.to_datetime(df['day'])
        df.set_index('day', inplace=True)
        df.index.name = ''
        
        if end_date and frequency in ['240m', '1200m', '7200m']:
            return df[df.index <= end_date][-mcount:]
        
        return df
    
    def _get_realtime_sina(self, code: str) -> Dict[str, Any]:
        """新浪实时行情"""
        url = f'http://hq.sinajs.cn/list={code}'
        resp = self.session.get(url, timeout=5)
        resp.encoding = 'gbk'
        text = resp.text
        
        if 'var hq_str_' not in text:
            raise ValueError(f"Invalid response for {code}")
        
        data_str = text.split('"')[1]
        if not data_str:
            raise ValueError(f"Empty data for {code}")
        
        parts = data_str.split(',')
        
        if len(parts) < 32:
            raise ValueError(f"Incomplete data for {code}")
        
        return {
            "ticker": code,
            "name": parts[0],
            "open": float(parts[1]) if parts[1] else None,
            "prev_close": float(parts[2]) if parts[2] else None,
            "price": float(parts[3]) if parts[3] else None,
            "high": float(parts[4]) if parts[4] else None,
            "low": float(parts[5]) if parts[5] else None,
            "volume": float(parts[8]) if parts[8] else None,
            "amount": float(parts[9]) if parts[9] else None,
            "bid1_volume": float(parts[10]) if parts[10] else None,
            "bid1_price": float(parts[11]) if parts[11] else None,
            "ask1_volume": float(parts[20]) if parts[20] else None,
            "ask1_price": float(parts[21]) if parts[21] else None,
            "date": parts[30],
            "time": parts[31],
            "timestamp": datetime.datetime.now().isoformat(),
        }
    
    def _get_realtime_tx(self, code: str) -> Dict[str, Any]:
        """腾讯实时行情"""
        url = f'http://qt.gtimg.cn/q={code}'
        resp = self.session.get(url, timeout=5)
        resp.encoding = 'gbk'
        text = resp.text
        
        for line in text.split('\n'):
            if f'v_{code}' in line:
                start = line.find('"') + 1
                end = line.rfind('"')
                if start > 0 and end > start:
                    parts = line[start:end].split('~')
                    if len(parts) > 45:
                        price = float(parts[3]) if parts[3] else None
                        prev_close = float(parts[4]) if parts[4] else None
                        change = price - prev_close if price and prev_close else None
                        change_pct = (change / prev_close * 100) if change and prev_close else None
                        
                        return {
                            "ticker": code,
                            "name": parts[1],
                            "price": price,
                            "prev_close": prev_close,
                            "open": float(parts[5]) if parts[5] else None,
                            "volume": float(parts[6]) if parts[6] else None,
                            "high": float(parts[33]) if parts[33] else None,
                            "low": float(parts[34]) if parts[34] else None,
                            "amount": float(parts[37]) if parts[37] else None,
                            "change": change,
                            "change_percent": change_pct,
                            "pe_ratio": float(parts[39]) if parts[39] else None,
                            "market_cap": float(parts[45]) if parts[45] else None,
                            "timestamp": datetime.datetime.now().isoformat(),
                        }
        
        raise ValueError(f"Failed to parse data for {code}")
    
    def _get_batch_realtime_sina(self, codes: List[str]) -> List[Dict[str, Any]]:
        """批量获取新浪实时行情"""
        codes_str = ','.join(codes)
        url = f'http://hq.sinajs.cn/list={codes_str}'
        resp = self.session.get(url, timeout=10)
        resp.encoding = 'gbk'
        
        results = []
        for line in resp.text.strip().split('\n'):
            if 'var hq_str_' not in line:
                continue
            
            code = line.split('var hq_str_')[1].split('=')[0]
            data_str = line.split('"')[1] if '"' in line else ''
            
            if not data_str:
                results.append({"ticker": code, "error": "No data"})
                continue
            
            parts = data_str.split(',')
            if len(parts) < 32:
                results.append({"ticker": code, "error": "Incomplete data"})
                continue
            
            results.append({
                "ticker": code,
                "name": parts[0],
                "price": float(parts[3]) if parts[3] else None,
                "prev_close": float(parts[2]) if parts[2] else None,
                "open": float(parts[1]) if parts[1] else None,
                "high": float(parts[4]) if parts[4] else None,
                "low": float(parts[5]) if parts[5] else None,
                "volume": float(parts[8]) if parts[8] else None,
                "amount": float(parts[9]) if parts[9] else None,
                "timestamp": datetime.datetime.now().isoformat(),
            })
        
        return results


_default_client: Optional[AshareQuoteClient] = None


def get_ashare_client() -> AshareQuoteClient:
    """获取默认客户端"""
    global _default_client
    if _default_client is None:
        _default_client = AshareQuoteClient()
    return _default_client
