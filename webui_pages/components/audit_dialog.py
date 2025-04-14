import streamlit as st
import pandas as pd
from datetime import datetime
from ..db.audit_db import AuditDatabase
import re

def extract_audit_result(text: str) -> tuple[int, str]:
    """从标准格式的审核结果中提取分数和通过状态"""
    # 提取分数
    score_patterns = [
        r'总分[:：]\s*?(\d+)\s*分',
        r'总分[:：]?\s*?(\d+)',
        r'总\s*分[:：]?\s*?(\d+)',
        r'得分[:：]?\s*?(\d+)',
    ]
    
    score = None
    for pattern in score_patterns:
        match = re.search(pattern, text.replace('\n', ' '), re.MULTILINE)
        if match:
            try:
                score = int(match.group(1))
                break
            except ValueError:
                continue
    
    if score is None:
        return None, None
        
    # 根据分数确定是否通过
    status_match = re.search(r'审核结果[：:]\s*([^（(（\n]*)', text)
    if not status_match:
        st.error("未能从文本中提取到审核状态")
        return None, None
        
    # 只保留"通过"或"不通过"状态
    status = status_match.group(1).strip()
    status = "通过" if "通过" in status else "不通过"
    
    return score, status

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
                st.write("Debug: 数据库记录数:", len(records))
                # 处理记录数据
                for record in records:
                    # 提取纯状态信息
                    if record.get("是否通过"):
                        record["是否通过"] = "通过" if "通过" in record["是否通过"].split()[0] else "不通过"
                    
                    # 检查报告内容
                    if record.get("file_id"):
                        db = AuditDatabase()
                        report_content = db.get_report(record["file_id"])
                        record["下载报告"] = "📥" if report_content else "-"
                        st.write(f"Debug: file_id {record['file_id']} 报告长度:", len(report_content) if report_content else 0)
                
                # 转换为DataFrame
                df = pd.DataFrame(
                    records,
                    columns=['文件名', '状态', '审核时间', '总分', '是否通过', '下载报告']
                )
                
                # 显示数据表格时确保"是否通过"列只显示状态
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
                            help="审核结果状态"
                        ),
                        "下载报告": st.column_config.Column(
                            "下载报告",
                            width="small",
                        )
                    }
                )
                
                # 在表格下方显示下载按钮
                st.write("#### 下载审核报告")
                for record in records:
                    if record.get("file_id"):
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.write(f"📄 {record['文件名']}")
                        with col2:
                            db = AuditDatabase()
                            report_content = db.get_report(record["file_id"])
                            if report_content:
                                st.download_button(
                                    "📥 下载报告",
                                    report_content,
                                    file_name=f"{record['文件名']}_审核报告.md",
                                    mime="text/markdown",
                                    key=f"download_{record['file_id']}",
                                    use_container_width=True
                                )
                            else:
                                st.write("无报告")
                
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

def show_audit_records(records):
    for record in records:
        # ... 其他列的显示代码 ...
        
        # 添加下载报告按钮列
        if record.get("file_id"):
            db = AuditDatabase()
            report_content = db.get_report(record["file_id"])
            if report_content:
                # 生成下载按钮
                filename = f"{record['文件名']}_审核报告.md"
                st.download_button(
                    "📥 下载报告",
                    report_content,
                    file_name=filename,
                    mime="text/markdown",
                    key=f"download_{record['file_id']}"
                )
            else:
                st.text("无报告")

# 在保存审核结果时确保保存报告内容
def update_record(self, file_id: str, status: str, score: int, is_pass: str, report_content: str):
    """更新审核记录"""
    try:
        conn = self._get_connection()
        c = conn.cursor()
        
        # 更新记录,包括报告内容
        c.execute("""
            UPDATE audit_records 
            SET status = ?, score = ?, is_pass = ?, report_content = ?
            WHERE file_id = ?
        """, (status, score, is_pass, report_content, file_id))
        
        conn.commit()
        return True
    except Exception as e:
        print(f"Error updating record: {e}")
        return False
    finally:
        conn.close()