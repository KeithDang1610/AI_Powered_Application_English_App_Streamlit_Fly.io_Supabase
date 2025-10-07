# utils/vocab_utils.py
from datetime import datetime, timedelta
from typing import List
import streamlit as st
# from .state_utils import now_str

# dic = pyphen.Pyphen(lang='en')

def normalize_word(w: str) -> str:
    return w.strip().lower()

def search_vocab_for_user(conn, user_id: int, query: str = None, limit: int = 25,
                          min_rank: int = None, max_rank: int = None, syll_filter: int = None):
    cur = conn.cursor()
    conditions = []
    params = [user_id]   # cho uv.user_id = %s


    if query:
        q = f"%{query.lower()}%"
        conditions.append("w.word ILIKE %s")
        params.append(q)

    if min_rank is not None:
        conditions.append("w.ranking >= %s")
        params.append(min_rank)

    if max_rank is not None:
        conditions.append("w.ranking <= %s")
        params.append(max_rank)

    if syll_filter is not None:
        conditions.append("w.syllables = %s")
        params.append(syll_filter)
    
    conditions.append("uv.word_id IS NULL")

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
    sql = f"""SELECT w.id, w.word, w.phonetic, w.example, w.ranking, w.syllables
              FROM words w 
              LEFT JOIN user_vocab uv ON w.id = uv.word_id AND uv.user_id = %s
              {where_clause}
              ORDER BY w.ranking ASC 
              LIMIT %s"""

    params.append(limit)   # cuối cùng cho LIMIT %s


    try:
        cur.execute(sql, tuple(params))
        return cur.fetchall()
    except Exception as e:
        st.error(f"❌ There is no word in your current vocab or you already learned it")
        return []
    # cur.execute(sql, tuple(params))
    # return cur.fetchall()


def get_vocab_by_id(conn, vid: int):
    cur = conn.cursor()
    cur.execute("SELECT id, word, phonetic, example, ranking, syllables FROM words WHERE id = %s", (vid,))
    r = cur.fetchone()
    return r

def add_user_vocab(conn, user_id: int, vocab_id: int):
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO user_vocab (user_id, word_id, repetition_count, next_due, appearances)
        VALUES (%s, %s, 0, DATE('now'), 0)
        ON CONFLICT DO NOTHING;
    """, (user_id, vocab_id))
    conn.commit()

def schedule_next_repetition(conn, user_id: int, vocab_id: int, success: bool):
    """
    Basic spaced repetition schedule:
    - on first success => +1 day
    - second => +3 days
    - third => +7 days
    - else => +14 days
    If failure (success==False), schedule back to tomorrow.
    Also increment appearances.
    """
    cur = conn.cursor()
    cur.execute("SELECT repetition_count, appearances FROM user_vocab WHERE user_id=%s AND word_id=%s", (user_id, vocab_id))
    row = cur.fetchone()
    if not row:
        add_user_vocab(conn, user_id, vocab_id)
        repetition_count = 0
        appearances = 0
    else:
        repetition_count, appearances = row
    if success:
        repetition_count += 1
        if repetition_count == 1:
            delta = 1
        elif repetition_count == 2:
            delta = 3
        elif repetition_count == 3:
            delta = 7
        else:
            delta = 14
    else:
        delta = 1  # retry tomorrow
    next_due = (datetime.utcnow() + timedelta(days=delta)).date().isoformat()
    appearances += 1
    cur.execute("""
        UPDATE user_vocab SET repetition_count=%s, next_due=%s, appearances=%s WHERE user_id=%s AND word_id=%s
    """, (repetition_count, next_due, appearances, user_id, vocab_id))
    conn.commit()

def mark_word_confirmation(conn, user_id: int, vocab_id: int):
    cur = conn.cursor()
    cur.execute("UPDATE user_vocab SET learned=1 WHERE user_id=%s AND word_id=%s", (user_id, vocab_id))
    conn.commit()

def get_due_for_user(conn, user_id: int, limit: int = 10):
    cur = conn.cursor()
    cur.execute("""
        SELECT uv.id, v.id, v.word, v.phonetic, v.example, uv.repetition_count, uv.appearances
        FROM user_vocab uv JOIN words v ON uv.word_id = v.id
        WHERE uv.user_id = %s AND (uv.next_due IS NULL OR DATE(uv.next_due) <= DATE('now')) AND uv.learned = 0
        ORDER BY uv.next_due
        LIMIT %s
    """, (user_id, limit))
    rows = cur.fetchall()
    return rows
