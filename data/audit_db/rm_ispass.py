import sqlite3
import re

def simplify_is_pass_directly(db_path):
    """
    直接修改数据库中的is_pass列，只保留"通过"或"不通过"
    
    参数:
        db_path: SQLite3数据库文件路径
    """
    try:
        # 连接数据库
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 获取所有记录
        cursor.execute("SELECT rowid, is_pass FROM audit_records")
        records = cursor.fetchall()
        update_count = 0
        
        for rowid, is_pass in records:
            # 提取"通过"或"不通过"
            match = re.match(r'^(通过|不通过)', str(is_pass))
            if match:
                new_value = match.group(1)
                # 只在不同时才更新
                if new_value != is_pass:
                    cursor.execute("UPDATE audit_records SET is_pass = ? WHERE rowid = ?", 
                                 (new_value, rowid))
                    update_count += 1
        
        # 提交更改
        conn.commit()
        print(f"处理完成，共更新 {update_count}/{len(records)} 条记录")
        
    except sqlite3.Error as e:
        print(f"数据库错误: {e}")
        conn.rollback()
    except Exception as e:
        print(f"发生错误: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    db_path = '/share/home/wuqingyao_zhangboyang/anaconda3/envs/doc_review/lib/python3.10/site-packages/chatchat/data/audit_db/audit_records.db'
    simplify_is_pass_directly(db_path)
    
