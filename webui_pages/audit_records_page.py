import streamlit as st
import pandas as pd
from datetime import datetime
from .db.audit_db import AuditDatabase

def show_audit_records_page():
    st.set_page_config(page_title="审核记录", layout="wide")
    
    st.write("## 📋 审核记录列表")
    
    # 初始化数据库连接
    db = AuditDatabase()
    page = st.session_state.get("audit_page", 1)
    per_page = 10
    
    # 获取总记录数和总页数
    total_records = db.get_total_count()
    total_pages = (total_records + per_page - 1) // per_page
    
    # 添加搜索和筛选功能
    col1, col2 = st.columns([2, 1])
    with col1:
        search_term = st.text_input("🔍 搜索文件名", key="search_file")
    with col2:
        status_filter = st.selectbox(
            "状态筛选",
            ["全部", "待审核", "正在处理文档", "正在模型推理", "已审核", "审核失败"],
            key="status_filter"
        )
    
    if total_records > 0:
        # 获取记录
        records = db.get_records(page=page, per_page=per_page)
        if records:
            # 转换为DataFrame并显示
            df = pd.DataFrame(
                records,
                columns=['文件名', '状态', '审核时间', '总分', '是否通过', '单位', 'file_id']
            )
            
            # 为已审核的记录添加下载按钮，未审核的显示"未完成"
            df['操作'] = df.apply(
                lambda x: '📥 下载报告' if x['状态'] == '已审核' else '未完成',
                axis=1
            )
            
            # 使用 data_editor 显示表格，并配置按钮列和单位列
            edited_df = st.data_editor(
                df.drop(columns=['file_id']),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "操作": st.column_config.ButtonColumn(
                        "操作",
                        help="点击下载审核报告",
                        width="small",
                    ),
                    "单位": st.column_config.TextColumn(
                        "单位",
                        help="申报单位",
                        width="medium",
                    )
                },
                disabled=["文件名", "状态", "审核时间", "总分", "是否通过", "单位"]
            )
            
            # 处理按钮点击事件
            for index, row in edited_df.iterrows():
                if row["操作"] == "📥 下载报告":
                    report_content = db.get_report(df.iloc[index]['file_id'])
                    if report_content:
                        st.download_button(
                            label=f"确认下载 {df.iloc[index]['文件名']} 的审核报告",
                            data=report_content,
                            file_name=f"{datetime.now():%Y-%m-%d_%H-%M}_{df.iloc[index]['文件名']}_审核报告.md",
                            mime="text/markdown",
                            key=f"download_{df.iloc[index]['file_id']}",
                        )
            
            # 分页控制
            cols = st.columns(5)
            if cols[0].button("⏮️ 首页", disabled=page<=1):
                st.session_state.audit_page = 1
                st.rerun()
            if cols[1].button("⏪ 上一页", disabled=page<=1):
                st.session_state.audit_page = max(1, page - 1)
                st.rerun()
            
            cols[2].write(f"第 {page} / {total_pages} 页")
            
            if cols[3].button("⏩ 下一页", disabled=page>=total_pages):
                st.session_state.audit_page = min(total_pages, page + 1)
                st.rerun()
            if cols[4].button("⏭️ 末页", disabled=page>=total_pages):
                st.session_state.audit_page = total_pages
                st.rerun()
    else:
        st.info("暂无审核记录")
    
    # 返回主页按钮
    if st.button("◀️ 返回主页", use_container_width=True):
        st.session_state.show_audit_records = False
        st.rerun()