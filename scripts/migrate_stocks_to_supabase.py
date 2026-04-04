#!/usr/bin/env python3
"""
将本地股票数据迁移到 Supabase

使用前:
1. 在 Supabase 创建项目
2. 执行下面的 SQL 创建表
3. 设置环境变量 SUPABASE_URL 和 SUPABASE_ANON_KEY
4. 运行此脚本

SQL Schema (在 Supabase SQL Editor 中执行):
```sql
-- 创建股票表
CREATE TABLE IF NOT EXISTS stocks (
    id SERIAL PRIMARY KEY,
    code VARCHAR(20) NOT NULL,
    name VARCHAR(100) NOT NULL,
    ticker VARCHAR(20) NOT NULL UNIQUE,
    market VARCHAR(10) NOT NULL,
    exchange VARCHAR(20),
    pinyin VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 创建索引加速搜索
CREATE INDEX IF NOT EXISTS idx_stocks_ticker ON stocks(ticker);
CREATE INDEX IF NOT EXISTS idx_stocks_name ON stocks(name);
CREATE INDEX IF NOT EXISTS idx_stocks_market ON stocks(market);
CREATE INDEX IF NOT EXISTS idx_stocks_pinyin ON stocks(pinyin);

-- 创建全文搜索索引（可选，更快）
CREATE INDEX IF NOT EXISTS idx_stocks_name_trgm ON stocks USING gin(name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_stocks_ticker_trgm ON stocks USING gin(ticker gin_trgm_ops);

-- 如果使用 trigram 索引，需要先启用扩展
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```
"""
import os
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
from dotenv import load_dotenv

load_dotenv(project_root / ".env")


def get_pinyin(name: str) -> str:
    """获取中文名称的拼音首字母"""
    try:
        from pypinyin import pinyin, Style
        if any('\u4e00' <= c <= '\u9fff' for c in str(name)):
            py = pinyin(str(name), style=Style.FIRST_LETTER)
            return "".join([p[0] for p in py]).lower()
    except:
        pass
    return ""


def load_local_stocks() -> pd.DataFrame:
    """加载本地股票数据"""
    data_dir = project_root / "data" / "stock_lists"
    dfs = []
    
    # 上交所
    sse_path = data_dir / "SSE.csv"
    if sse_path.exists():
        df = pd.read_csv(sse_path)
        df["market"] = "CN"
        df["exchange"] = "SSE"
        df["ticker"] = "sh" + df["code"].astype(str).str.zfill(6)
        dfs.append(df)
        print(f"Loaded {len(df)} SSE stocks")
    
    # 深交所
    szse_path = data_dir / "SZSE.csv"
    if szse_path.exists():
        df = pd.read_csv(szse_path)
        df["market"] = "CN"
        df["exchange"] = "SZSE"
        df["ticker"] = "sz" + df["code"].astype(str).str.zfill(6)
        dfs.append(df)
        print(f"Loaded {len(df)} SZSE stocks")
    
    # 港交所
    hkex_path = data_dir / "HKEX.csv"
    if hkex_path.exists():
        df = pd.read_csv(hkex_path)
        df["market"] = "HK"
        df["exchange"] = "HKEX"
        df["ticker"] = "hk" + df["code"].astype(str).str.zfill(5)
        dfs.append(df)
        print(f"Loaded {len(df)} HKEX stocks")
    
    # NASDAQ
    nasdaq_path = data_dir / "NASDAQ.csv"
    if nasdaq_path.exists():
        df = pd.read_csv(nasdaq_path)
        df["market"] = "US"
        df["exchange"] = "NASDAQ"
        df["ticker"] = df["code"].astype(str).str.upper()
        dfs.append(df)
        print(f"Loaded {len(df)} NASDAQ stocks")
    
    # NYSE
    nyse_path = data_dir / "NYSE.csv"
    if nyse_path.exists():
        df = pd.read_csv(nyse_path)
        df["market"] = "US"
        df["exchange"] = "NYSE"
        df["ticker"] = df["code"].astype(str).str.upper()
        dfs.append(df)
        print(f"Loaded {len(df)} NYSE stocks")
    
    if not dfs:
        raise ValueError("No stock data found!")
    
    all_stocks = pd.concat(dfs, ignore_index=True)
    
    # 添加拼音
    print("Generating pinyin...")
    all_stocks["pinyin"] = all_stocks["name"].apply(get_pinyin)
    
    # 确保列名正确
    all_stocks["code"] = all_stocks["code"].astype(str)
    
    return all_stocks


def migrate_to_supabase(df: pd.DataFrame, batch_size: int = 500):
    """将数据迁移到 Supabase"""
    from supabase import create_client
    
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_ANON_KEY")
    
    if not url or not key:
        raise ValueError("Please set SUPABASE_URL and SUPABASE_ANON_KEY environment variables")
    
    client = create_client(url, key)
    
    # 准备数据
    records = []
    for _, row in df.iterrows():
        records.append({
            "code": str(row["code"]),
            "name": str(row["name"]),
            "ticker": str(row["ticker"]),
            "market": str(row["market"]),
            "exchange": str(row.get("exchange", "")),
            "pinyin": str(row.get("pinyin", "")),
        })
    
    print(f"Total records to upload: {len(records)}")
    
    # 分批上传
    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        try:
            # 使用 upsert 避免重复
            client.table("stocks").upsert(batch, on_conflict="ticker").execute()
            print(f"Uploaded batch {i // batch_size + 1}/{(len(records) + batch_size - 1) // batch_size}")
        except Exception as e:
            print(f"Error uploading batch: {e}")
            # 尝试逐条插入来找出问题记录
            for record in batch:
                try:
                    client.table("stocks").upsert([record], on_conflict="ticker").execute()
                except Exception as e2:
                    print(f"Failed to insert {record['ticker']}: {e2}")
    
    print("Migration complete!")


def main():
    print("Loading local stock data...")
    df = load_local_stocks()
    print(f"Total stocks: {len(df)}")
    
    print("\nMigrating to Supabase...")
    migrate_to_supabase(df)


if __name__ == "__main__":
    main()
