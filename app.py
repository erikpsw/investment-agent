import sys
from pathlib import Path

# 设置包路径，使相对导入正常工作
app_dir = Path(__file__).parent
parent_dir = app_dir.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

import streamlit as st

st.set_page_config(
    page_title="Investment Agent",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

from investment.ui.dashboard import render_dashboard


def main():
    with st.sidebar:
        st.title("📈 Investment Agent")
        st.divider()
        
        page = st.radio(
            "导航",
            [
                "🏠 仪表盘",
                "📊 个股分析",
                "📄 财报管理",
                "🔍 财报搜索",
                "📈 财务图表",
            ],
            key="navigation"
        )
        
        st.divider()
        
        with st.expander("⚙️ 设置"):
            st.text_input("API Key", type="password", key="api_key_input")
            st.selectbox("LLM 模型", ["Qwen/Qwen3.5-27B"], key="llm_model")
        
        st.divider()
        st.caption("v0.1.0 | 仅供研究学习")
    
    if page == "🏠 仪表盘":
        render_dashboard()
    
    elif page == "📊 个股分析":
        from investment.ui.stock_detail import render_stock_detail
        render_stock_detail()
    
    elif page == "📄 财报管理":
        from investment.ui.report_viewer import render_report_viewer
        render_report_viewer()
    
    elif page == "🔍 财报搜索":
        from investment.ui.report_search import render_report_search
        render_report_search()
    
    elif page == "📈 财务图表":
        from investment.ui.financial_charts import render_financial_charts
        render_financial_charts()


if __name__ == "__main__":
    main()
