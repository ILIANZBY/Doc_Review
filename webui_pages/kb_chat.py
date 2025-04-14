from datetime import datetime
import uuid
from typing import List, Dict
import pandas as pd
import re
import openai
import streamlit as st
import streamlit_antd_components as sac
from streamlit_chatbox import *
from streamlit_extras.bottom_container import bottom
import zipfile
import tempfile
import os
import mimetypes

from chatchat.settings import Settings
from chatchat.server.knowledge_base.utils import LOADER_DICT
from chatchat.server.utils import get_config_models, get_config_platforms, get_default_llm, api_address
from chatchat.webui_pages.dialogue.dialogue import (save_session, restore_session, rerun,
                                                    get_messages_history, upload_temp_docs,
                                                    add_conv, del_conv, clear_conv)
from chatchat.webui_pages.utils import *

from chatchat.webui_pages.db.audit_db import AuditDatabase
from chatchat.webui_pages.components.audit_dialog import show_audit_records_dialog

chat_box = ChatBox(assistant_avatar=get_img_base64("chatchat_icon_blue_square_v2.png"))


def init_widgets():
    st.session_state.setdefault("history_len", Settings.model_settings.HISTORY_LEN)
    st.session_state.setdefault("selected_kb", Settings.kb_settings.DEFAULT_KNOWLEDGE_BASE)
    st.session_state.setdefault("kb_top_k", Settings.kb_settings.VECTOR_SEARCH_TOP_K)
    st.session_state.setdefault("se_top_k", Settings.kb_settings.SEARCH_ENGINE_TOP_K)
    st.session_state.setdefault("score_threshold", Settings.kb_settings.SCORE_THRESHOLD)
    st.session_state.setdefault("search_engine", Settings.kb_settings.DEFAULT_SEARCH_ENGINE)
    st.session_state.setdefault("return_direct", False)
    st.session_state.setdefault("cur_conv_name", chat_box.cur_chat_name)
    st.session_state.setdefault("last_conv_name", chat_box.cur_chat_name)
    st.session_state.setdefault("file_chat_id", None)
    st.session_state.setdefault("audit_files", [])  # 存储审核文件信息的列表
    st.session_state.setdefault("current_audit_file", None)  # 当前正在审核的文件
    st.session_state.setdefault("audit_prompt_template", """请对以下申报书进行全面深入的审核。即使在缺乏某些具体信息的情况下，也请基于已有内容进行评估：

{document}

审核要求：
1. 基于文档中可见的信息进行评分
2. 对于文档中未提及或不清楚的部分，应在评分时适当扣分并在建议中指出
3. 即使信息不完整，也要给出合理的评分和建议
4. 如果某些关键信息缺失，该维度的得分不应超过该维度分值的60%

评分标准（总分100分）：
1. 文档完整性（20分）
- 完整填写各项内容，附件材料齐全且符合要求（18-20分）
- 存在少量缺失或未填写的部分（14-17分）
- 缺失较多内容或附件材料不齐全（0-13分）

[其他评分标准保持不变...]

请严格按照以下格式输出审核结果，确保分值部分格式统一：

==== 评分详情 ====
1. 文档完整性：[数字]分
[具体分析理由和建议]

2. 信息准确性：[数字]分
[具体分析理由和建议]

3. 教学内容与设计：[数字]分
[具体分析理由和建议]

4. 教学资源与支持：[数字]分
[具体分析理由和建议]

5. 教学效果与评价：[数字]分
[具体分析理由和建议]

==== 总评 ====
总分：[数字]分
审核结果：[通过/不通过]

[注意：总分必须是上述5项分值的总和，且为整数；结果只能是"通过"或"不通过"，不要添加其他说明]

==== 主要优点 ====
1. ...
2. ...
3. ...

==== 存在问题 ====
1. ...
2. ...
3. ...

==== 改进建议 ====
1. ...
2. ...
3. ...

请注意：
1. 分数必须是整数，不要包含小数点
2. 分数后面必须加"分"字
3. "总分"和"审核结果"必须严格按照上述格式输出
4. 不要在分数部分添加任何额外的说明文字
5. 评分时即使信息不完整也要给出具体分值
""")
    st.session_state.setdefault("show_audit_records", False)  # 控制审核记录显示状态
    st.session_state.setdefault("audit_page", 1)

def process_uploaded_files(files):
    """处理上传的文件，支持单个文件和文件夹"""
    processed_files = []
    
    for file in files:
        # 检查是否是文件夹（ZIP格式）
        if file.name.endswith('.zip'):
            with zipfile.ZipFile(file, 'r') as zip_ref:
                # 创建临时目录
                with tempfile.TemporaryDirectory() as temp_dir:
                    zip_ref.extractall(temp_dir)
                    # 遍历解压后的文件
                    for root, _, filenames in os.walk(temp_dir):
                        for filename in filenames:
                            # 检查文件扩展名是否在支持的格式列表中
                            if any(filename.endswith(ext) for ext in [i for ls in LOADER_DICT.values() for i in ls]):
                                file_path = os.path.join(root, filename)
                                with open(file_path, 'rb') as f:
                                    # 创建类似于 UploadedFile 的对象
                                    processed_files.append({
                                        'file': f.read(),
                                        'name': filename,
                                        'type': mimetypes.guess_type(filename)[0]
                                    })
        else:
            # 单个文件直接添加
            processed_files.append(file)
    
    return processed_files

def extract_audit_result(text: str) -> tuple[int, str]:
    """从标准格式的审核结果中提取分数和通过状态"""
    # 调试输出
    st.write("正在提取分数信息...")
    st.write("原始文本片段：", text[text.find("总分"):text.find("总分")+20])  # 添加文本片段调试
    
    # 更健壮的正则模式
    score_patterns = [
        r'总分[:：]\s*?(\d+)\s*分',  # 处理标准格式
        r'总分[:：]?\s*?(\d+)', # 更宽松的格式
        r'总\s*分[:：]?\s*?(\d+)', # 处理可能的空格
        r'得分[:：]?\s*?(\d+)',  # 处理其他可能的表述
    ]
    
    score = None
    matched_pattern = None
    
    for pattern in score_patterns:
        match = re.search(pattern, text.replace('\n', ' '), re.MULTILINE)
        if match:
            try:
                score = int(match.group(1))
                matched_pattern = pattern
                st.write(f"Debug: 成功匹配模式 '{pattern}', 提取到分数: {score}")
                break
            except ValueError as e:
                st.write(f"Debug: 数值转换失败: {e}")
                continue
    
    if not score:
        st.error("未能从文本中提取到总分")
        st.write("Debug: 尝试的所有模式都失败")
        return None, None
        
    status_match = re.search(r'审核结果[：:]\s*([^（(（]*)', text.replace('\n', ' '))
    if not status_match:
        st.error("未能从文本中提取到审核状态")
        return None, None
        
    status = status_match.group(1).strip()
    
    # 添加调试信息
    st.write(f"Debug: 最终提取结果 - 总分: {score}, 状态: {status}")
    st.write(f"Debug: 使用的匹配模式: {matched_pattern}")
    
    return score, status

def export_all_reports():
    """导出所有审核报告为ZIP文件"""
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            db = AuditDatabase()
            records = db.get_all_records()
            
            if not records:
                st.warning("没有找到任何审核记录")
                return None
            
            reports_created = 0
            for record in records:
                if record.get("report_content"):
                    try:
                        filename = f"{record['文件名']}_审核报告.md"
                        file_path = os.path.join(temp_dir, filename)
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(record["report_content"])
                        reports_created += 1
                    except Exception as e:
                        st.error(f"处理记录时出错 ({record.get('文件名', '未知文件')}): {str(e)}")
                        continue
            
            if reports_created == 0:
                st.warning("没有可导出的报告内容")
                return None
            
            # 创建ZIP文件
            zip_path = os.path.join(temp_dir, "所有审核报告.zip")
            with zipfile.ZipFile(zip_path, 'w') as zipf:
                for root, _, files in os.walk(temp_dir):
                    for file in files:
                        if file.endswith('.md'):
                            zipf.write(os.path.join(root, file), file)
            
            with open(zip_path, 'rb') as f:
                return f.read()
    except Exception as e:
        st.error(f"导出报告时发生错误: {str(e)}")
        return None

def update_record(self, file_id: str, status: str, score: int, is_pass: str, report_content: str):
    """更新审核记录"""
    try:
        conn = self._get_connection()
        c = conn.cursor()
        
        # 1. 检查现有记录
        c.execute("SELECT * FROM audit_records WHERE file_id = ?", (file_id,))
        existing = c.fetchone()
        
        if existing:
            # 更新记录
            c.execute("""
                UPDATE audit_records 
                SET status = ?,
                    score = ?,
                    is_pass = ?,
                    report_content = ?,
                    update_time = CURRENT_TIMESTAMP
                WHERE file_id = ?
            """, (status, score, is_pass.split()[0], report_content, file_id))
        else:
            # 插入新记录
            c.execute("""
                INSERT INTO audit_records 
                (file_id, status, score, is_pass, report_content, create_time, update_time)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """, (file_id, status, score, is_pass.split()[0], report_content))
        
        conn.commit()
        
        # 验证保存是否成功
        c.execute("SELECT report_content FROM audit_records WHERE file_id = ?", (file_id,))
        saved = c.fetchone()
        if not saved or not saved[0]:
            print(f"Warning: Report content not saved for file_id {file_id}")
            return False
            
        return True
    except Exception as e:
        print(f"Error updating record: {e}")
        return False
    finally:
        if conn:
            conn.close()

def kb_chat(api: ApiRequest):
    ctx = chat_box.context
    ctx.setdefault("uid", uuid.uuid4().hex)
    ctx.setdefault("file_chat_id", None)
    ctx.setdefault("llm_model", get_default_llm())
    ctx.setdefault("temperature", Settings.model_settings.TEMPERATURE)
    init_widgets()

    # sac on_change callbacks not working since st>=1.34
    if st.session_state.cur_conv_name != st.session_state.last_conv_name:
        save_session(st.session_state.last_conv_name)
        restore_session(st.session_state.cur_conv_name)
        st.session_state.last_conv_name = st.session_state.cur_conv_name

    @st.experimental_dialog("模型配置", width="large")
    def llm_model_setting():
        cols = st.columns(3)
        platforms = ["所有"] + list(get_config_platforms())
        platform = cols[0].selectbox("选择模型平台", platforms, key="platform")
        llm_models = list(
            get_config_models(
                model_type="llm", platform_name=None if platform == "所有" else platform
            )
        )
        llm_models += list(
            get_config_models(
                model_type="image2text", platform_name=None if platform == "所有" else platform
            )
        )
        llm_model = cols[1].selectbox("选择LLM模型", llm_models, key="llm_model")
        temperature = cols[2].slider("Temperature", 0.0, 1.0, key="temperature")
        system_message = st.text_area("System Message:", key="system_message")
        if st.button("OK"):
            rerun()

    @st.experimental_dialog("重命名会话")
    def rename_conversation():
        name = st.text_input("会话名称")
        if st.button("OK"):
            chat_box.change_chat_name(name)
            restore_session()
            st.session_state["cur_conv_name"] = name
            rerun()

    with st.sidebar:
        tabs = st.tabs(["RAG 配置", "会话设置"])
        with tabs[0]:
            dialogue_modes = ["知识库问答",
                              "文件对话",
                              "搜索引擎问答",
                              "审核评价模式",
                              ]
            dialogue_mode = st.selectbox("请选择对话模式：",
                                         dialogue_modes,
                                         key="dialogue_mode",
                                         )
            placeholder = st.empty()
            st.divider()
            prompt_name = "default"
            history_len = st.number_input("历史对话轮数：", 0, 20, key="history_len")
            kb_top_k = st.number_input("匹配知识条数：", 1, 20, key="kb_top_k")
            score_threshold = st.slider("知识匹配分数阈值：", 0.0, 2.0, step=0.01, key="score_threshold")
            return_direct = st.checkbox("仅返回检索结果", key="return_direct")

            def on_kb_change():
                st.toast(f"已加载知识库： {st.session_state.selected_kb}")

            with placeholder.container():
                if dialogue_mode == "知识库问答":
                    kb_list = [x["kb_name"] for x in api.list_knowledge_bases()]
                    selected_kb = st.selectbox(
                        "请选择知识库：",
                        kb_list,
                        on_change=on_kb_change,
                        key="selected_kb",
                    )
                elif dialogue_mode == "文件对话":
                    files = st.file_uploader("上传知识文件：",
                                            [i for ls in LOADER_DICT.values() for i in ls],
                                            accept_multiple_files=True,
                                            )
                    if st.button("开始上传", disabled=len(files) == 0):
                        st.session_state["file_chat_id"] = upload_temp_docs(files, api)
                elif dialogue_mode == "审核评价模式":
                    col1, col2, col3, col4 = st.columns([2, 2, 1, 1])
                    
                    with col1:
                        kb_list = [x["kb_name"] for x in api.list_knowledge_bases()]
                        selected_kb = st.selectbox(
                            "选择审核知识库：",
                            kb_list,
                            on_change=on_kb_change,
                            key="selected_kb",
                        )
                    
                    with col2:
                        files = st.file_uploader("上传待审核文件或文件夹（ZIP）：",
                                                [i for ls in LOADER_DICT.values() for i in ls] + ['zip'],
                                                accept_multiple_files=True,
                                                )
                    
                    with col3:
                        if st.button("📋 审核记录", use_container_width=True, key="show_audit_btn"):
                            st.switch_page("pages/audit_records_page.py")
                    
                    with col4:
                        export_data = export_all_reports()
                        if export_data is not None:
                            if st.download_button(
                                "📥 导出全部",
                                data=export_data,
                                file_name="所有审核报告.zip",
                                mime="application/zip",
                                use_container_width=True
                            ):
                                st.success("已导出所有审核报告")
                        else:
                            st.button("📥 导出全部", disabled=True, use_container_width=True)
                    
                    st.divider()
                    
                    # 上传按钮
                    if st.button("开始审核", disabled=len(files) == 0):
                        # 处理上传的文件
                        processed_files = process_uploaded_files(files)
                        
                        if not processed_files:
                            st.error("没有找到可处理的文件")
                            st.stop()
                        
                        # 创建进度条
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        
                        db = AuditDatabase()
                        total_files = len(processed_files)
                        
                        for idx, file in enumerate(processed_files, 1):
                            status_text.text(f"正在处理 {file.name} ({idx}/{total_files})")
                            
                            # 上传单个文件并获取chat_id
                            file_chat_id = upload_temp_docs([file], api)
                            
                            # 保存文件信息到数据库
                            file_info = {
                                "文件名": file.name,
                                "状态": "正在处理文档",
                                "审核时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "file_id": file_chat_id,
                                "是否通过": "待审核",
                                "总分": "-"
                            }
                            db.add_record(file_info)
                            
                            # 触发该文件的自动审核
                            st.session_state["file_chat_id"] = file_chat_id
                            st.session_state["current_audit_filename"] = file.name
                            st.session_state["trigger_auto_audit"] = True
                            
                            # 更新进度
                            progress_bar.progress(idx/total_files)
                        
                        status_text.text("所有文件处理完成！")
                        st.success(f"已上传并开始审核 {total_files} 个文件")
                        st.rerun()
                elif dialogue_mode == "搜索引擎问答":
                    search_engine_list = list(Settings.tool_settings.search_internet["search_engine_config"])
                    search_engine = st.selectbox(
                        label="请选择搜索引擎",
                        options=search_engine_list,
                        key="search_engine",
                    )

        with tabs[1]:
            cols = st.columns(3)
            conv_names = chat_box.get_chat_names()

            def on_conv_change():
                print(conversation_name, st.session_state.cur_conv_name)
                save_session(conversation_name)
                restore_session(st.session_state.cur_conv_name)

            conversation_name = sac.buttons(
                conv_names,
                label="当前会话：",
                key="cur_conv_name",
                on_change=on_conv_change,
            )
            chat_box.use_chat_name(conversation_name)
            conversation_id = chat_box.context["uid"]
            if cols[0].button("新建", on_click=add_conv):
                ...
            if cols[1].button("重命名"):
                rename_conversation()
            if cols[2].button("删除", on_click=del_conv):
                ...

    chat_box.output_messages()
    chat_input_placeholder = "请输入对话内容，换行请使用Shift+Enter。"

    llm_model = ctx.get("llm_model")

    with bottom():
        cols = st.columns([1, 0.2, 15,  1])
        if cols[0].button(":gear:", help="模型配置"):
            widget_keys = ["platform", "llm_model", "temperature", "system_message"]
            chat_box.context_to_session(include=widget_keys)
            llm_model_setting()
        if cols[-1].button(":wastebasket:", help="清空对话"):
            chat_box.reset_history()
            rerun()
        prompt = cols[2].chat_input(chat_input_placeholder, key="prompt")
    if dialogue_mode == "审核评价模式" and st.session_state.get("trigger_auto_audit", False):
        st.session_state["trigger_auto_audit"] = False
        
        if st.session_state.get("file_chat_id") is None:
            st.error("文件上传失败，请重试")
            st.stop()
        
        knowledge_id = st.session_state.get("file_chat_id")
        selected_kb = st.session_state.get("selected_kb")
        
        # 显示当前正在处理的文件名
        current_file = st.session_state.get("current_audit_filename", "未知文件")
        st.info(f"正在审核: {current_file}")
        
        # 获取上传文档的内容
        api_url = api_address(is_public=True)
        client = openai.Client(base_url=f"{api_url}/knowledge_base/temp_kb/{knowledge_id}", api_key="NONE")
        
        # 1. 首先获取文档内容
        doc_messages = [{"role": "user", "content": "请返回完整的文档内容"}]
        doc_response = client.chat.completions.create(
            messages=doc_messages, 
            model=llm_model,
            extra_body={"return_direct": True}
        )
        document_content = "\n\n".join(doc_response.docs) if hasattr(doc_response, 'docs') else ""
        
        # 2. 获取知识库参考信息
        kb_client = openai.Client(base_url=f"{api_url}/knowledge_base/local_kb/{selected_kb}", api_key="NONE")
        kb_messages = [{"role": "user", "content": "请提供审核标准和参考信息"}]
        kb_response = kb_client.chat.completions.create(
            messages=kb_messages,
            model=llm_model,
            extra_body={"return_direct": True}
        )
        kb_content = "\n\n".join(kb_response.docs) if hasattr(kb_response, 'docs') else "暂无参考信息"
        
        # 3. 将文档内容插入到审核模板中
        audit_template = st.session_state.get("audit_prompt_template")
        filled_template = audit_template.format(document=document_content)
        
        # 4. 生成完整的提示词
        system_prompt = f"""你是一个专业的项目申报书审核专家。请按照以下模板严格审核评价。
即使在信息不完整的情况下，也要基于已有内容给出合理的评估。

审核知识库参考信息：
{kb_content}

审核模板：
{filled_template}

注意事项：
1. 即使某些信息不完整，也必须给出评分和评价
2. 对于信息缺失的部分，在对应维度予以适当扣分
3. 评分时应重点关注已有信息的质量
4. 在建议部分明确指出需要补充的信息
"""

        messages = [{"role": "system", "content": system_prompt}]
        
        chat_box.user_say("自动审核评价请求")
        
        # 使用知识库问答模式获取审核标准
        client = openai.Client(base_url=f"{api_url}/knowledge_base/local_kb/{selected_kb}", api_key="NONE")
        
        chat_box.ai_say([
            Markdown("...", in_expander=True, title="审核知识检索结果", state="running", expanded=return_direct),
            f"正在分析文件并参考审核知识库 `{selected_kb}` 进行评审...",
        ])
        
        # 后续处理逻辑保持不变
        text = ""
        full_report_text = ""  # 累积完整的审核报告文本
        first = True
        try:
            for i, file_info in enumerate(st.session_state.audit_files):
                
                if file_info["file_id"] == knowledge_id:
                    st.session_state.audit_files[i]["状态"] = "正在模型推理"
            
            for d in client.chat.completions.create(messages=messages, model=llm_model, stream=True):
                if first:
                    chat_box.update_msg("\n\n".join(d.docs), element_index=0, streaming=False, state="complete")
                    chat_box.update_msg("", streaming=False)
                    first = False
                    continue
                chunk = d.choices[0].delta.content or ""
                text += chunk
                full_report_text += chunk  # 累积完整报告
                chat_box.update_msg(text.replace("\n", "\n\n"), streaming=True)
            
            chat_box.update_msg(text, streaming=False)
            
            # 提取总分和通过状态
            score, status = extract_audit_result(full_report_text)

            # 在保存报告前添加验证和错误处理
            if score is not None:
                try:
                    db = AuditDatabase()
                    # 1. 先更新记录基本信息
                    update_success = db.update_record(
                        file_id=knowledge_id,
                        status="已审核",
                        score=score,
                        is_pass=status,  # 只保存"通过"或"不通过"
                        report_content=full_report_text
                    )
                    
                    # 2. 验证更新和报告保存是否成功
                    saved_record = db.get_record_by_id(knowledge_id)
                    if not saved_record or not saved_record.get("report_content"):
                        st.error("报告保存失败")
                        st.write("Debug: 保存的记录状态:", saved_record)
                    else:
                        st.success(f"审核完成 - 总分：{score}分，状态：{status}")
                        
                except Exception as e:
                    st.error(f"保存记录时出错: {str(e)}")
                    st.write("Debug: 错误详情:", e)
            else:
                st.error("保存失败：缺少必要信息")
                st.write(f"Debug: knowledge_id: {knowledge_id}, report length: {len(full_report_text) if full_report_text else 0}")

            # 更新会话状态中的文件信息
            for i, file_info in enumerate(st.session_state.audit_files):
                if file_info["file_id"] == knowledge_id:
                    st.session_state.audit_files[i]["状态"] = "已审核" if score is not None else "已审核(解析失败)"
                    st.session_state.audit_files[i]["总分"] = score if score is not None else "-"
                    st.session_state.audit_files[i]["是否通过"] = status if status is not None else "未知"
                    break

            # 显示审核结果
            result_message = f"审核完成 - 总分：{score}分，状态：{status}" if score is not None else "审核完成但无法解析分数"
            st.success(result_message)

            # 生成下载按钮
            original_filename = st.session_state.get("current_audit_filename", "未命名文件")
            report_filename = f"{original_filename}的审核报告.md"
            st.info(f"正在生成审核报告：{report_filename}")

            st.download_button(
                "📥 下载审核报告",
                full_report_text,
                file_name=report_filename,
                mime="text/markdown",
                use_container_width=True,
            )

            st.session_state["last_audit_result"] = full_report_text
            st.session_state["audit_time"] = datetime.now()
            
        except Exception as e:
            for i, file_info in enumerate(st.session_state.audit_files):
                if file_info["file_id"] == knowledge_id:
                    st.session_state.audit_files[i]["状态"] = "审核失败"
            st.error(str(e))
    if prompt:
        history = get_messages_history(ctx.get("history_len", 0))
        messages = history + [{"role": "user", "content": prompt}]
        chat_box.user_say(prompt)

        extra_body = dict(
            top_k=kb_top_k,
            score_threshold=score_threshold,
            temperature=ctx.get("temperature"),
            prompt_name=prompt_name,
            return_direct=return_direct,
        )
    
        api_url = api_address(is_public=True)
        if dialogue_mode == "知识库问答":
            client = openai.Client(base_url=f"{api_url}/knowledge_base/local_kb/{selected_kb}", api_key="NONE")
            chat_box.ai_say([
                Markdown("...", in_expander=True, title="知识库匹配结果", state="running", expanded=return_direct),
                f"正在查询知识库 `{selected_kb}` ...",
            ])
        elif dialogue_mode == "文件对话":
            if st.session_state.get("file_chat_id") is None:
                st.error("请先上传文件再进行对话")
                st.stop()
            knowledge_id=st.session_state.get("file_chat_id")
            client = openai.Client(base_url=f"{api_url}/knowledge_base/temp_kb/{knowledge_id}", api_key="NONE")
            chat_box.ai_say([
                Markdown("...", in_expander=True, title="知识库匹配结果", state="running", expanded=return_direct),
                f"正在查询文件 `{st.session_state.get('file_chat_id')}` ...",
            ])
        else:
            client = openai.Client(base_url=f"{api_url}/knowledge_base/search_engine/{search_engine}", api_key="NONE")
            chat_box.ai_say([
                Markdown("...", in_expander=True, title="知识库匹配结果", state="running", expanded=return_direct),
                f"正在执行 `{search_engine}` 搜索...",
            ])

        text = ""
        full_text = ""  # 新增：用于累积完整响应
        first = True
        try:
            for d in client.chat.completions.create(messages=messages, model=llm_model, stream=True):
                if first:
                    chat_box.update_msg("\n\n".join(d.docs), element_index=0, streaming=False, state="complete")
                    chat_box.update_msg("", streaming=False)
                    first = False
                    continue
                
                chunk = d.choices[0].delta.content or ""
                text += chunk
                full_text += chunk  # 累积完整响应
                chat_box.update_msg(text.replace("\n", "\n\n"), streaming=True)
            
            chat_box.update_msg(text, streaming=False)
            
            # 在流式结束后使用完整文本提取结果
            score, status = extract_audit_result(full_text)  # 使用完整文本
            
            # 添加调试输出到前端
            st.text_area("完整审核结果(调试用)", full_text, height=300)
            st.write(f"调试提取结果 - 分数: {score}, 状态: {status}")
            
            if score is not None:
                db = AuditDatabase()
                db.update_record(
                    file_id=knowledge_id,
                    status="已审核",
                    score=score,
                    is_pass=status,
                    report_content=full_text  # 保存完整报告
                )
                st.success(f"审核完成 - 总分：{score}分，状态：{status}")
            else:
                st.error(f"无法提取审核结果，请检查输出格式。原始文本:\n{full_text[:500]}...")
        except Exception as e:
            st.error(e.body)

    now = datetime.now()
    with tabs[1]:
        cols = st.columns(2)
        export_btn = cols[0]
        if cols[1].button(
            "清空对话",
            use_container_width=True,
        ):
            chat_box.reset_history()
            rerun()

    export_btn.download_button(
        "导出记录",
        "".join(chat_box.export2md()),
        file_name=f"{now:%Y-%m-%d %H.%M}_对话记录.md",
        mime="text/markdown",
        use_container_width=True,
    )
