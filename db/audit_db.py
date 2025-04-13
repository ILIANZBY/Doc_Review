import sqlite3
from datetime import datetime
import os

class AuditDatabase:
    def __init__(self, db_path="audit_records.db"):
        # 确保数据库目录存在
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS audit_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    audit_time TIMESTAMP,
                    score INTEGER,
                    is_pass TEXT,
                    file_id TEXT UNIQUE,
                    report_content TEXT,    # 添加报告内容字段
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

    def add_record(self, file_info):
        with sqlite3.connect(self.db_path) as conn:
            # 将中文键名转换为英文字段名
            mapped_info = {
                'file_name': file_info['文件名'],
                'status': file_info['状态'],
                'audit_time': file_info['审核时间'],
                'score': None if file_info['总分'] == '-' else file_info['总分'],
                'is_pass': file_info['是否通过'],
                'file_id': file_info['file_id'],
                'report_content': file_info.get('report_content')
            }
            
            # 添加调试日志
            print(f"Debug: Mapped file info: {mapped_info}")
            
            conn.execute('''
                INSERT INTO audit_records 
                (file_name, status, audit_time, score, is_pass, file_id, report_content)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                mapped_info['file_name'],
                mapped_info['status'],
                mapped_info['audit_time'],
                mapped_info['score'],
                mapped_info['is_pass'],
                mapped_info['file_id'],
                mapped_info['report_content']
            ))

    def update_record(self, file_id, status, score=None, is_pass=None, report_content=None):
        """更新审核记录"""
        with sqlite3.connect(self.db_path) as conn:
            try:
                # 添加调试日志
                print(f"正在更新记录 - file_id: {file_id}")
                print(f"状态: {status}, 分数: {score}, 是否通过: {is_pass}")
                print(f"报告内容长度: {len(report_content) if report_content else 0}")
                
                # 移除必要字段验证，允许部分字段为空
                if not report_content:
                    print("警告：报告内容为空")
                    return False
                
                # 转换报告内容为字符串
                if not isinstance(report_content, str):
                    report_content = str(report_content)
                
                # 更新记录
                conn.execute('''
                    UPDATE audit_records 
                    SET status = ?,
                        score = ?,
                        is_pass = ?,
                        audit_time = ?,
                        report_content = ?
                    WHERE file_id = ?
                ''', (
                    status,
                    score,  # 允许为 None
                    is_pass,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    report_content,
                    file_id
                ))
                
                conn.commit()
                return True
                
            except Exception as e:
                print(f"更新记录时出错: {str(e)}")
                conn.rollback()
                raise

    def get_records(self, page=1, per_page=10):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            offset = (page - 1) * per_page
            cursor = conn.execute('''
                SELECT 
                    file_name AS "文件名",
                    status AS "状态",
                    audit_time AS "审核时间",
                    score AS "总分",
                    is_pass AS "是否通过",
                    file_id,
                    report_content
                FROM audit_records
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            ''', (per_page, offset))
            
            records = []
            for row in cursor:
                # 转换为字典并直接使用中文键名
                record = dict(row)
                records.append(record)
                
            return records

    def get_total_count(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('SELECT COUNT(*) FROM audit_records')
            return cursor.fetchone()[0]