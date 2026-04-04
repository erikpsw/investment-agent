import streamlit as st
from investment.reports import ReportRAG
from investment.agents.graph import run_report_qa
from investment.ui.components import render_search_results, render_disclaimer


def render_report_search():
    """渲染财报语义搜索页面"""
    st.title("🔍 财报语义搜索")
    
    st.markdown("""
    使用自然语言搜索财报内容，或向 AI 提问关于财报的问题。
    
    **示例问题：**
    - 公司的主营业务收入是多少？
    - 研发费用占营收的比例？
    - 有哪些主要风险因素？
    """)
    
    tab1, tab2 = st.tabs(["语义搜索", "AI 问答"])
    
    with tab1:
        render_search_tab()
    
    with tab2:
        render_qa_tab()
    
    st.divider()
    render_disclaimer()


def render_search_tab():
    """渲染搜索标签页"""
    col1, col2 = st.columns([3, 1])
    
    with col1:
        query = st.text_input(
            "搜索内容",
            placeholder="输入要搜索的内容...",
            key="search_query"
        )
    
    with col2:
        stock_filter = st.text_input(
            "限定股票",
            placeholder="可选",
            key="search_stock_filter"
        )
    
    n_results = st.slider("返回结果数", 1, 20, 5, key="search_n_results")
    
    if st.button("🔍 搜索", type="primary"):
        if not query:
            st.warning("请输入搜索内容")
            return
        
        with st.spinner("搜索中..."):
            rag = ReportRAG()
            results = rag.search(
                query,
                stock_code=stock_filter if stock_filter else None,
                n_results=n_results
            )
        
        if results:
            st.success(f"找到 {len(results)} 条相关内容")
            render_search_results(results)
        else:
            st.info("未找到相关内容，请尝试其他关键词或先导入财报")


def render_qa_tab():
    """渲染问答标签页"""
    st.subheader("AI 财报问答")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        question = st.text_area(
            "您的问题",
            placeholder="输入关于财报的问题...",
            height=100,
            key="qa_question"
        )
    
    with col2:
        stock_filter = st.text_input(
            "限定股票",
            placeholder="可选",
            key="qa_stock_filter"
        )
    
    if st.button("🤖 获取答案", type="primary"):
        if not question:
            st.warning("请输入问题")
            return
        
        with st.spinner("AI 正在分析财报并生成答案..."):
            try:
                result = run_report_qa(
                    question,
                    ticker=stock_filter if stock_filter else ""
                )
                
                answer = result.get("report_qa_answer", "")
                sources = result.get("report_search_results", [])
                
                if answer:
                    st.markdown("### 回答")
                    st.markdown(answer)
                    
                    if sources:
                        with st.expander(f"📚 参考来源 ({len(sources)} 条)"):
                            render_search_results(sources)
                else:
                    st.warning("未能生成答案，请确保已导入相关财报")
                
                if result.get("errors"):
                    with st.expander("⚠️ 处理过程中的问题"):
                        for error in result["errors"]:
                            st.error(error)
                            
            except Exception as e:
                st.error(f"问答失败: {e}")
    
    with st.expander("💡 使用提示"):
        st.markdown("""
        1. 首先在"财报管理"页面下载并索引财报
        2. 提问时尽量具体，如"2023年营业收入"比"收入"更准确
        3. 可以限定股票代码缩小搜索范围
        4. AI 回答基于已索引的财报内容，请核实关键数据
        """)
