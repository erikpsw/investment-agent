from api.routes.disclosure import _documents_from_cninfo_rows


def test_cninfo_rows_become_filtered_pdf_documents():
    rows = [
        {
            "公告标题": "贵州茅台2025年年度报告",
            "公告链接": "http://www.cninfo.com.cn/new/disclosure/detail?announcementId=1234567890",
            "公告时间": "2026-03-30 00:00:00",
            "简称": "贵州茅台",
        },
        {
            "公告标题": "贵州茅台2025年年度报告摘要",
            "公告链接": "http://www.cninfo.com.cn/new/disclosure/detail?announcementId=999",
            "公告时间": "2026-03-30 00:00:00",
        },
    ]

    documents = _documents_from_cninfo_rows(rows, "annual")

    assert len(documents) == 1
    assert documents[0].title == "贵州茅台2025年年度报告"
    assert documents[0].url == "https://static.cninfo.com.cn/finalpage/2026-03-30/1234567890.PDF"
    assert documents[0].source == "巨潮资讯"


def test_cninfo_all_category_accepts_interim_and_quarterly_reports():
    rows = [
        {
            "公告标题": "公司2025年半年度报告",
            "公告链接": "announcementId=100",
            "公告时间": "2025-08-01",
        },
        {
            "公告标题": "公司2025年第三季度报告",
            "公告链接": "announcementId=101",
            "公告时间": "2025-10-01",
        },
    ]

    assert len(_documents_from_cninfo_rows(rows, "all")) == 2
