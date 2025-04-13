import streamlit as st
import pandas as pd
from ..db.audit_db import AuditDatabase

def show_audit_records_dialog():
    # 使用container而不是dialog
    with st.container():
        st.write("### 📋 审核记录列表")
        
        db = AuditDatabase()
        page = st.session_state.get("audit_page", 1)
        per_page = 10
        
        # 获取总记录数和总页数
        total_records = db.get_total_count()
        total_pages = (total_records + per_page - 1) // per_page
        
        if total_records > 0:
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(f"共 {total_records} 条记录")
            with col2:
                if st.button("❌ 关闭", key="close_audit_records", use_container_width=True):
                    st.session_state.show_audit_records = False
                    st.rerun()
            
            # 获取当前页的记录
            records = db.get_records(page=page, per_page=per_page)
            
            if records:
                # 转换为DataFrame
                df = pd.DataFrame(
                    records,
                    columns=['文件名', '状态', '审核时间', '总分', '是否通过']
                )
                
                # 显示数据表格
                st.dataframe(
                    df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "文件名": st.column_config.TextColumn(
                            "文件名",
                            width="medium",
                        ),
                        "状态": st.column_config.TextColumn(
                            "状态",
                            width="small",
                        ),
                        "审核时间": st.column_config.TextColumn(
                            "审核时间",
                            width="medium",
                        ),
                        "总分": st.column_config.NumberColumn(
                            "总分",
                            width="small",
                        ),
                        "是否通过": st.column_config.TextColumn(
                            "是否通过",
                            width="small",
                        ),
                    }
                )
                
                # 分页控制器
                cols = st.columns(4)
                if cols[0].button("首页", key="first_page", disabled=page<=1):
                    st.session_state.audit_page = 1
                    st.rerun()
                if cols[1].button("上一页", key="prev_page", disabled=page<=1):
                    st.session_state.audit_page = page - 1
                    st.rerun()
                
                cols[2].write(f"第 {page} / {total_pages} 页")
                
                if cols[3].button("下一页", key="next_page", disabled=page>=total_pages):
                    st.session_state.audit_page = page + 1
                    st.rerun()
        else:
            st.info("暂无审核记录")
            if st.button("关闭", key="close_empty_records"):
                st.session_state.show_audit_records = False
                st.rerun()