"""
SEC EDGAR 财报获取工具 - 下载和解析美股 10-K/10-Q HTM 文件
"""
import re
import json
import time
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
import httpx
from bs4 import BeautifulSoup

STORAGE_DIR = Path(__file__).resolve().parent.parent.parent / "storage"
SEC_DIR = STORAGE_DIR / "sec_filings"
TEXT_DIR = STORAGE_DIR / "pdf_texts"  # 复用 PDF 的文本目录

for d in [SEC_DIR, TEXT_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# SEC 要求的 User-Agent
SEC_HEADERS = {
    "User-Agent": "InvestmentAgent research@example.com",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def get_recent_filings(ticker: str, filing_type: str = "10-K", count: int = 5) -> List[Dict[str, Any]]:
    """获取最近的 SEC 文件列表"""
    filings = []
    
    try:
        # 使用 SEC EDGAR 全文搜索 API
        url = f"https://efts.sec.gov/LATEST/search-index?q=%22{ticker}%22&dateRange=custom&startdt=2020-01-01&enddt=2030-12-31&forms={filing_type}"
        
        # 备用：直接使用公司搜索
        search_url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company={ticker}&type={filing_type}&dateb=&owner=include&count={count}&output=atom"
        
        with httpx.Client(timeout=30, headers=SEC_HEADERS, follow_redirects=True) as client:
            resp = client.get(search_url)
            
            # 解析 Atom feed
            soup = BeautifulSoup(resp.text, 'xml')
            entries = soup.find_all('entry')
            
            for entry in entries[:count]:
                title = entry.find('title')
                link = entry.find('link')
                updated = entry.find('updated')
                
                if title and link:
                    filing_url = link.get('href', '')
                    # 从 filing URL 提取 accession number
                    acc_match = re.search(r'/(\d{10}-\d{2}-\d{6})', filing_url)
                    
                    filings.append({
                        'title': title.text,
                        'url': filing_url,
                        'date': updated.text[:10] if updated else '',
                        'accession': acc_match.group(1) if acc_match else '',
                    })
    except Exception as e:
        print(f"[SEC] Error getting filings for {ticker}: {e}")
    
    return filings


def get_filing_documents(filing_url: str) -> List[Dict[str, str]]:
    """获取 filing 中的文档列表"""
    documents = []
    base_url = filing_url.rsplit('/', 1)[0]
    
    try:
        with httpx.Client(timeout=30, headers=SEC_HEADERS, follow_redirects=True) as client:
            resp = client.get(filing_url)
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # 查找文档链接
            for row in soup.find_all('tr'):
                cells = row.find_all('td')
                if len(cells) >= 4:
                    link_elem = row.find('a')
                    if link_elem:
                        name = link_elem.text.strip()
                        doc_type = cells[3].text.strip() if len(cells) > 3 else ''
                        
                        if name.endswith('.htm') or name.endswith('.html'):
                            documents.append({
                                'type': doc_type,
                                'name': name,
                                'url': f"{base_url}/{name}",
                            })
    except Exception as e:
        print(f"[SEC] Error getting documents from {filing_url}: {e}")
    
    return documents


def parse_htm_to_text(htm_content: str) -> str:
    """将 HTM 内容解析为纯文本 - 改进版，去除重复"""
    try:
        soup = BeautifulSoup(htm_content, 'html.parser')
        
        # 移除脚本、样式和 XBRL 头部
        for tag in soup.find_all(['script', 'style', 'meta', 'link', 'ix:header']):
            tag.decompose()
        
        # 使用 body 的直接文本，避免嵌套元素重复
        body = soup.find('body') or soup
        
        # 提取所有文本块，使用集合去重
        seen_texts = set()
        lines = []
        
        # 处理表格 - 按行提取
        for table in body.find_all('table'):
            for row in table.find_all('tr'):
                cells = [td.get_text(strip=True) for td in row.find_all(['td', 'th'])]
                row_text = ' | '.join(c for c in cells if c)
                if row_text and len(row_text) > 5:
                    text_key = row_text[:100].lower()
                    if text_key not in seen_texts:
                        seen_texts.add(text_key)
                        lines.append(row_text)
            table.decompose()  # 移除已处理的表格
        
        # 处理段落和标题
        for elem in body.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'li']):
            text = elem.get_text(separator=' ', strip=True)
            if text and len(text) > 10:
                # 使用前100字符作为去重键
                text_key = text[:100].lower()
                if text_key not in seen_texts:
                    seen_texts.add(text_key)
                    lines.append(text)
        
        # 合并并清理
        full_text = '\n'.join(lines)
        
        # 清理多余空白
        full_text = re.sub(r'\n{3,}', '\n\n', full_text)
        full_text = re.sub(r' {2,}', ' ', full_text)
        
        return full_text
        
    except Exception as e:
        print(f"[SEC] Error parsing HTM: {e}")
        return ""


def fetch_and_parse_10k(ticker: str) -> Optional[str]:
    """获取并解析最新的 10-K 报告，返回文本内容"""
    ticker = ticker.upper()
    
    # 检查缓存的文本文件
    text_file = TEXT_DIR / f"{ticker}_10-K.txt"
    if text_file.exists() and (datetime.now().timestamp() - text_file.stat().st_mtime) < 86400 * 30:
        print(f"[SEC] Using cached text: {text_file}")
        return text_file.read_text(encoding='utf-8')
    
    print(f"[SEC] Fetching 10-K for {ticker}")
    
    try:
        with httpx.Client(timeout=60, headers=SEC_HEADERS, follow_redirects=True) as client:
            # 获取最近的 10-K filing
            search_url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={ticker}&type=10-K&dateb=&owner=include&count=3&output=atom"
            resp = client.get(search_url)
            soup = BeautifulSoup(resp.text, 'xml')
            entries = soup.find_all('entry')
            
            if not entries:
                print(f"[SEC] No 10-K filings found for {ticker}")
                return None
            
            entry = entries[0]
            link = entry.find('link')
            filing_url = link.get('href', '')
            base_url = filing_url.rsplit('/', 1)[0]
            
            print(f"[SEC] Found filing: {entry.find('title').text[:50]}...")
            
            time.sleep(0.3)  # 避免限流
            
            # 获取 filing index 页面
            resp2 = client.get(filing_url)
            soup2 = BeautifulSoup(resp2.text, 'html.parser')
            
            # 找主文档
            main_doc_url = None
            for row in soup2.find_all('tr'):
                cells = row.find_all('td')
                if len(cells) >= 4:
                    link_elem = row.find('a')
                    if link_elem:
                        name = link_elem.text.strip()
                        doc_type = cells[3].text.strip() if len(cells) > 3 else ''
                        
                        if '10-K' in doc_type and (name.endswith('.htm') or name.endswith('.html')):
                            main_doc_url = f"{base_url}/{name}"
                            print(f"[SEC] Found main doc: {name}")
                            break
            
            if not main_doc_url:
                print(f"[SEC] No main document found")
                return None
            
            # 下载 HTM
            print(f"[SEC] Downloading: {main_doc_url}")
            resp3 = client.get(main_doc_url)
            htm_content = resp3.text
            
            # 解析为文本
            text = parse_htm_to_text(htm_content)
            
            if text and len(text) > 1000:
                # 保存文本缓存
                text_file.write_text(text, encoding='utf-8')
                print(f"[SEC] Saved text ({len(text)} chars) to {text_file}")
                return text
            else:
                print(f"[SEC] Parsed text too short: {len(text)} chars")
                return None
                
    except Exception as e:
        print(f"[SEC] Error fetching 10-K for {ticker}: {e}")
        import traceback
        traceback.print_exc()
        return None


def extract_key_financials(text: str) -> Dict[str, Any]:
    """从 SEC 10-K 文本中提取关键财务数据"""
    financials = {}
    
    # 查找 SUMMARY RESULTS OF OPERATIONS 或类似表格
    patterns = {
        'revenue': [
            r'(?:Total\s+)?Revenue\s*\|\s*\$\s*\|\s*([\d,]+)',  # 表格格式: Revenue | $ | 281,724
            r'(?:Total\s+)?Revenue[s]?\s*\$?\s*([\d,]+)\s*(?:million|billion)?',
            r'Net\s+revenues?\s*\$?\s*([\d,]+)',
        ],
        'net_income': [
            r'Net\s+income\s*\|\s*\$?\s*\|?\s*([\d,]+)',  # 表格格式
            r'Net\s+[Ii]ncome\s*\$?\s*([\d,]+)\s*(?:million)?',
        ],
        'operating_income': [
            r'Operating\s+income\s*\|\s*\$?\s*\|?\s*([\d,]+)',  # 表格格式
            r'Operating\s+[Ii]ncome\s*\$?\s*([\d,]+)\s*(?:million)?',
        ],
        'gross_margin': [
            r'Gross\s+margin\s*\|\s*\$?\s*\|?\s*([\d,]+)',  # 表格格式
            r'Gross\s+[Mm]argin\s*\$?\s*([\d,]+)',
            r'Gross\s+profit\s*\$?\s*([\d,]+)',
        ],
        'eps': [
            r'Diluted\s+earnings\s+per\s+share\s*\|\s*\$?\s*\|?\s*([\d.]+)',  # 表格格式
            r'(?:Diluted\s+)?[Ee]arnings\s+per\s+share.*?\$?\s*([\d.]+)',
            r'EPS.*?\$?\s*([\d.]+)',
        ],
    }
    
    for key, pattern_list in patterns.items():
        for pattern in pattern_list:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                value = match.group(1).replace(',', '')
                try:
                    financials[key] = float(value)
                except:
                    financials[key] = value
                break
    
    return financials


def extract_sec_sections(text: str) -> Dict[str, str]:
    """从 SEC 10-K 文本中提取关键章节"""
    sections = {}
    
    # SEC 10-K 的标准章节
    sec_patterns = [
        (r"(?:ITEM|Item)\s*1[.\s]+Business", "business", r"(?:ITEM|Item)\s*1A"),
        (r"(?:ITEM|Item)\s*1A[.\s]+Risk\s*Factors", "risk_factors", r"(?:ITEM|Item)\s*1B"),
        (r"(?:ITEM|Item)\s*2[.\s]+Properties", "properties", r"(?:ITEM|Item)\s*3"),
        (r"(?:ITEM|Item)\s*6[.\s]+Selected\s*Financial", "financial_data", r"(?:ITEM|Item)\s*7"),
        (r"(?:ITEM|Item)\s*7[.\s]+Management.*Discussion", "md_and_a", r"(?:ITEM|Item)\s*7A"),
        (r"(?:ITEM|Item)\s*8[.\s]+Financial\s*Statements", "financial_statements", r"(?:ITEM|Item)\s*9"),
    ]
    
    for start_pattern, section_name, end_pattern in sec_patterns:
        try:
            start_match = re.search(start_pattern, text, re.IGNORECASE)
            if start_match:
                end_match = re.search(end_pattern, text[start_match.end():], re.IGNORECASE)
                if end_match:
                    section_text = text[start_match.start():start_match.end() + end_match.start()]
                else:
                    section_text = text[start_match.start():start_match.start() + 50000]
                
                sections[section_name] = section_text[:30000]
        except Exception:
            pass
    
    # 额外提取 SUMMARY RESULTS 部分
    summary_match = re.search(
        r'SUMMARY\s+RESULTS\s+OF\s+OPERATIONS.*?(?=Reportable\s+Segments|SEGMENT|$)',
        text, re.IGNORECASE | re.DOTALL
    )
    if summary_match:
        sections['summary_results'] = summary_match.group(0)[:10000]
    
    return sections


def get_sec_report_summary(ticker: str) -> Dict[str, Any]:
    """获取 SEC 报告摘要，用于分析"""
    text = fetch_and_parse_10k(ticker)
    if not text:
        return {"error": "Failed to fetch 10-K", "text": "", "sections": {}, "financials": {}}
    
    sections = extract_sec_sections(text)
    financials = extract_key_financials(text)
    
    # 构建摘要（取关键部分）
    summary_parts = []
    
    # 先放财务摘要
    if "summary_results" in sections:
        summary_parts.append(f"## Financial Summary\n{sections['summary_results'][:5000]}")
    
    if "business" in sections:
        summary_parts.append(f"## Business Overview\n{sections['business'][:5000]}")
    
    if "md_and_a" in sections:
        summary_parts.append(f"## Management Discussion\n{sections['md_and_a'][:8000]}")
    
    if "risk_factors" in sections:
        summary_parts.append(f"## Risk Factors\n{sections['risk_factors'][:5000]}")
    
    return {
        "ticker": ticker,
        "text": text[:50000] if text else "",
        "sections": sections,
        "financials": financials,
        "summary": "\n\n".join(summary_parts) if summary_parts else text[:20000],
    }
