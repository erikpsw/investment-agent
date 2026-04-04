import streamlit as st
from investment.reports import ReportDownloader, ReportParser, ReportRAG
from investment.ui.components import render_report_list, render_disclaimer


def render_report_viewer():
    """渲染财报查看器页面"""
    st.title("📄 财报管理")
    
    tab1, tab2, tab3 = st.tabs(["下载财报", "已下载", "已索引"])
    
    with tab1:
        render_download_tab()
    
    with tab2:
        render_downloaded_tab()
    
    with tab3:
        render_indexed_tab()
    
    st.divider()
    render_disclaimer()


def render_download_tab():
    """渲染下载财报标签页"""
    st.subheader("下载财报 PDF")
    
    col1, col2 = st.columns(2)
    
    with col1:
        stock_code = st.text_input(
            "股票代码",
            placeholder="6位数字，如 600519",
            key="download_stock_code"
        )
    
    with col2:
        report_type = st.selectbox(
            "报告类型",
            ["年度报告", "半年报", "季度报告", "业绩预告", "业绩快报"],
            key="download_report_type"
        )
    
    col1, col2 = st.columns(2)
    
    with col1:
        max_count = st.slider("最大下载数量", 1, 10, 3, key="download_max_count")
    
    with col2:
        auto_index = st.checkbox("下载后自动索引", value=True, key="auto_index")
    
    if st.button("🔍 搜索并下载", type="primary"):
        if not stock_code:
            st.warning("请输入股票代码")
            return
        
        downloader = ReportDownloader()
        
        with st.spinner("搜索财报..."):
            reports = downloader.search_reports(stock_code, report_type)
        
        if not reports or (len(reports) == 1 and "error" in reports[0]):
            st.error("未找到财报或搜索失败")
            return
        
        st.success(f"找到 {len(reports)} 份财报")
        
        for report in reports[:max_count]:
            st.write(f"📄 {report.get('title', 'N/A')}")
        
        with st.spinner("下载中..."):
            results = downloader.download_reports(stock_code, report_type, max_count)
        
        success_count = sum(1 for r in results if r.get("status") == "success")
        st.success(f"成功下载 {success_count}/{len(results)} 份")
        
        if auto_index and success_count > 0:
            with st.spinner("索引中..."):
                rag = ReportRAG()
                index_result = rag.ingest_report(stock_code, report_type, max_count)
                st.info(f"已索引 {index_result.get('indexed', 0)} 个文档块")


def render_downloaded_tab():
    """渲染已下载标签页"""
    st.subheader("已下载的财报")
    
    downloader = ReportDownloader()
    pdfs = downloader.list_downloaded()
    
    if not pdfs:
        st.info("暂无已下载的财报")
        return
    
    st.write(f"共 {len(pdfs)} 份")
    
    for pdf in pdfs:
        filename = pdf.split("/")[-1]
        col1, col2 = st.columns([4, 1])
        
        with col1:
            st.text(filename)
        
        with col2:
            if st.button("解析", key=f"parse_{filename}"):
                with st.spinner("解析中..."):
                    parser = ReportParser()
                    try:
                        parsed = parser.parse_pdf(pdf)
                        st.success(f"解析完成: {parsed.total_pages} 页, {len(parsed.tables)} 个表格")
                        
                        with st.expander("预览内容"):
                            st.text(parsed.text_content[:2000] + "...")
                    except Exception as e:
                        st.error(f"解析失败: {e}")


def render_indexed_tab():
    """渲染已索引标签页"""
    st.subheader("已索引的财报")
    
    rag = ReportRAG()
    
    try:
        reports = rag.list_indexed_reports()
        render_report_list(reports)
        
        stats = rag.get_stats()
        st.metric("总文档块数", stats["vectorstore"]["total_documents"])
        
    except Exception as e:
        st.error(f"获取索引信息失败: {e}")
