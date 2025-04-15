import sqlite3
from datetime import datetime
import os

class AuditDatabase:
    def __init__(self, db_path=None):
        if db_path is None:
            # 获取程序运行目录下的data文件夹
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            db_dir = os.path.join(base_dir, "data", "audit_db")
            # 创建数据库存储目录
            os.makedirs(db_dir, exist_ok=True)
            # 设置数据库文件路径
            self.db_path = os.path.join(db_dir, "audit_records.db")
        else:
            self.db_path = db_path
            # 确保数据库目录存在
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        self.init_db()

    def init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            # 先检查表是否存在
            cursor = conn.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='audit_records'
            """)
            table_exists = cursor.fetchone() is not None
            
            if not table_exists:
                # 如果表不存在，创建新表
                conn.execute('''
                    CREATE TABLE audit_records (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        file_name TEXT NOT NULL,
                        status TEXT NOT NULL,
                        audit_time TIMESTAMP,
                        score INTEGER,
                        is_pass TEXT,
                        unit TEXT DEFAULT '',
                        file_id TEXT,
                        report_content TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
            else:
                # 如果表已存在，检查是否有 unit 列
                cursor = conn.execute("PRAGMA table_info(audit_records)")
                columns = [column[1] for column in cursor.fetchall()]
                
                # 如果没有 unit 列，添加它
                if 'unit' not in columns:
                    conn.execute('ALTER TABLE audit_records ADD COLUMN unit TEXT DEFAULT ""')
                    conn.commit()

    def add_record(self, file_info: dict):
        """添加新的审核记录"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO audit_records 
                (file_id, file_name, status, audit_time, unit)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                file_info["file_id"],
                file_info["文件名"],
                "待审核",
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                file_info.get("单位", "")
            ))

    def update_record(self, file_id: str, status: str, score: int, is_pass: str, report_content: str):
        """更新审核记录"""
        with sqlite3.connect(self.db_path) as conn:
            try:
                conn.execute("""
                    UPDATE audit_records 
                    SET status = ?, 
                        score = ?, 
                        is_pass = ?, 
                        report_content = ?,
                        audit_time = CURRENT_TIMESTAMP
                    WHERE file_id = ?
                """, (status, score, is_pass, report_content, file_id))
                conn.commit()
                return True
            except Exception as e:
                print(f"更新记录失败: {str(e)}")
                return False

    def update_audit_status(self, file_id: str, status: str, score: float = None, passed: bool = None, report_content: str = None):
        """更新审核状态和结果"""
        with sqlite3.connect(self.db_path) as conn:
            if score is not None and passed is not None:
                conn.execute('''
                    UPDATE audit_records 
                    SET status=?, score=?, is_pass=?, audit_time=?, report_content=?
                    WHERE file_id=?
                ''', (
                    status,
                    score,
                    "通过" if passed else "不通过",
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    report_content,
                    file_id
                ))
            else:
                conn.execute('''
                    UPDATE audit_records 
                    SET status=?, audit_time=?
                    WHERE file_id=?
                ''', (
                    status,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    file_id
                ))

    def get_records(self, page: int = 1, per_page: int = 10):
        """获取审核记录列表"""
        offset = (page - 1) * per_page
        with sqlite3.connect(self.db_path) as conn:
            # 先获取所有列名
            cursor = conn.execute("PRAGMA table_info(audit_records)")
            columns = [column[1] for column in cursor.fetchall()]
            
            # 根据是否存在 unit 列构建查询语句
            if 'unit' in columns:
                select_sql = '''
                    SELECT file_name, status, audit_time, score, is_pass, unit, file_id ,report_content
                    FROM audit_records 
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                '''
            else:
                select_sql = '''
                    SELECT file_name, status, audit_time, score, is_pass, '' as unit, file_id ,report_content
                    FROM audit_records 
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                '''
                
            cursor = conn.execute(select_sql, (per_page, offset))
            
            records = []
            for row in cursor:
                records.append({
                    "文件名": row[0],
                    "状态": row[1],
                    "审核时间": row[2],
                    "总分": row[3] if row[3] is not None else "-",
                    "是否通过": row[4] if row[4] is not None else "待审核",
                    "单位": row[5] if row[5] is not None else "",
                    "file_id": row[6],
                    "report_content": row[7] if row[7] is not None else ""
                })
            return records

    def get_record_by_id(self, file_id: str) -> dict:
        """根据file_id获取审核记录"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row  # 启用字典形式的结果
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM audit_records WHERE file_id = ?", 
                (file_id,)
            )
            record = cursor.fetchone()
            
            if record:
                # 将sqlite3.Row对象转换为字典
                return dict(record)
            return None

    def get_report(self, file_id: str) -> str:
        """获取审核报告内容"""
        try:
            conn = self._get_connection()
            c = conn.cursor()
            c.execute("SELECT report_content FROM audit_records WHERE file_id = ?", (file_id,))
            result = c.fetchone()
            
            if result and result[0]:
                return result[0]
            
            print(f"No report content found for file_id: {file_id}")
            return None
        except Exception as e:
            print(f"Error getting report: {e}")
            return None
        finally:
            if conn:
                conn.close()

    def get_total_count(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('SELECT COUNT(*) FROM audit_records')
            return cursor.fetchone()[0]

    def get_all_records(self):
        """获取所有审核记录"""
        try:
            collection = self.db[self.collection_name]
            # 获取所有记录并转换为列表
            records = list(collection.find({}, {'_id': 0}))  # 排除 _id 字段
            return records
        except Exception as e:
            print(f"获取所有记录失败: {str(e)}")
            return []