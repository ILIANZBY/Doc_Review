import sqlite3
import pandas as pd

def export_to_excel(db_path, table_name, output_file):
    # 连接到SQLite数据库
    conn = sqlite3.connect(db_path)
    
    try:
        # 使用pandas读取数据库表
        df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
        
        # 将数据导出到Excel文件
        df.to_excel(output_file, index=False)
        print(f"数据已成功导出到 {output_file}")
    except Exception as e:
        print(f"导出过程中发生错误: {e}")
    finally:
        # 关闭数据库连接
        conn.close()

# 设置数据库路径、表名和输出文件名
db_path = '/share/home/wuqingyao_zhangboyang/anaconda3/envs/doc_review/lib/python3.10/site-packages/chatchat/data/audit_db/audit_records.db'  # 数据库文件路径
table_name = 'audit_records'  # 表名
output_file = '/share/home/wuqingyao_zhangboyang/anaconda3/envs/doc_review/lib/python3.10/site-packages/chatchat/data/audit_db/audit_records.xlsx'  # 输出的Excel文件名

# 调用函数导出数据
export_to_excel(db_path, table_name, output_file)