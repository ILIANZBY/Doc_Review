import streamlit as st
import pandas as pd
from datetime import datetime
from chatchat.webui_pages.db.audit_db import AuditDatabase

st.set_page_config(page_title="审核记录", layout="wide")

def show_audit_records():
    try:
        # 添加调试信息
        # st.write("Debug: 开始获取审核记录")
        
        db = AuditDatabase()
        page = st.session_state.get("audit_page", 1)
        per_page = 10
        
        if "download_index" not in st.session_state:
            st.session_state.download_index = None
        
        records = db.get_records(page=page, per_page=per_page)
        total_records = db.get_total_count()
        total_pages = (total_records + per_page - 1) // per_page
        
        # 打印原始记录用于调试
        # st.write("Debug: 获取到的记录：", records)
        
        if records:
            df_data = []
            
            for idx, record in enumerate(records):
                try:
                    # 检查报告内容
                    report_content = record.get('report_content')
                    # st.write(f"Debug: Record {idx} has report: {bool(report_content)}")
                    
                    file_info = {
                        "文件名": record["文件名"],
                        "状态": record["状态"],
                        "审核时间": record["审核时间"],
                        "总分": record["总分"] if record["总分"] is not None else "-",
                        "是否通过": record["是否通过"],
                        "操作": "",  # 这里先留空，后面用按钮填充
                        "下载报告": ""
                    }
                    
                    df_data.append(file_info)
                    
                except Exception as e:
                    st.error(f"处理记录时出错：{str(e)}")
                    st.write("问题记录：", record)
            print(file_info)
            df = pd.DataFrame(df_data)
            
            # 使用 AgGrid 或自定义组件来显示表格
            for i in range(len(df)):
                cols = st.columns([2, 1, 2, 1, 1, 2, 2])
                cols[0].write(df.iloc[i]["文件名"])
                cols[1].write(df.iloc[i]["状态"])
                cols[2].write(df.iloc[i]["审核时间"])
                cols[3].write(df.iloc[i]["总分"])
                cols[4].write(df.iloc[i]["是否通过"])
                cols[5].write(df.iloc[i]["操作"])
                
                # 修改下载按钮逻辑
                record = records[i]
                report_content = record.get('report_content')
                
                if report_content and record["状态"] == "已审核":
                    # st.write("Debug: 存在报告内容，长度:", len(report_content))
                    cols[6].download_button(
                        label="📥 下载报告",
                        data=report_content,
                        file_name=f"{record['文件名']}_审核报告.md",
                        mime="text/markdown",
                        key=f"download_{i}",
                    )
                else:
                    # st.write(f"Debug: 记录 {i} 无报告内容或未审核")
                    cols[6].write("-")
                
                # 添加分隔线
                st.markdown("---")
            
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
        if st.button("◀️ 返回主页"):
            st.switch_page("webui.py")
    except Exception as e:
        st.error(f"获取审核记录时出错：{str(e)}")

# 调用主函数
if __name__ == "__main__":
    show_audit_records()