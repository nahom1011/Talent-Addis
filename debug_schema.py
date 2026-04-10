import sqlite3

def check_msg_ids():
    try:
        conn = sqlite3.connect('d:/dbu talent/campus_talent_bot/campus_talent.db')
        row_factory = sqlite3.Row
        conn.row_factory = row_factory
        cursor = conn.cursor()
        
        print("Checking APPROVED posts message_ids...")
        cursor.execute("SELECT post_id, content_type, message_id FROM posts WHERE status='approved'")
        rows = cursor.fetchall()
        
        for row in rows:
            mid = row['message_id']
            mtype = type(mid)
            print(f"P:{row['post_id']} T:{row['content_type']} M:{mid} Type:{mtype}")
            
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_msg_ids()
