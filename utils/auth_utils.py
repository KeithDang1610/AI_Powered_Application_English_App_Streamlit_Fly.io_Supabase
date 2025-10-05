# utils/auth_utils.py
# import sqlite3
import bcrypt
# from database import get_pg_conn



def get_user_by_username(conn, username: str):
    cur = conn.cursor()
    cur.execute("SELECT id, username FROM users WHERE username = %s", (username,))
    row = cur.fetchone()
    if row:
        return {"id": row[0], "username": row[1]}
    return None

def login_user(conn, username: str, password: str) -> bool:
    cur = conn.cursor()
    cur.execute("SELECT password_hash FROM users WHERE username = %s", (username,))
    r = cur.fetchone()
    # print(r, type(r))

    if not r:
        return False
    pw_hash = r[0].encode()
    return bcrypt.checkpw(password.encode(), pw_hash)

def register_user(conn, username: str, password: str) -> bool:
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE username = %s", (username,))
    r = cur.fetchone()
    if r:
        return False
    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    cur.execute("INSERT INTO users (username, password_hash) VALUES (%s, %s)", (username, pw_hash))
    conn.commit()
    return True
