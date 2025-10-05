# app.py
import random
import streamlit as st
from pathlib import Path
from utils.auth_utils import login_user, register_user, get_user_by_username
from utils.vocab_utils import search_vocab_for_user, get_vocab_by_id, mark_word_confirmation, schedule_next_repetition, get_due_for_user, add_user_vocab
from utils.llm_utils import generate_passage_with_blanks, correct_sentence_with_llm, generate_passage_with_chunks, save_chunks_for_user
from utils.tts_utils import tts_button, tts_chunk_button, tts_passage_button
# from utils.state_utils import get_state
from database import get_pg_conn


def main():
    st.set_page_config(page_title="Personal English Vocab App")
    st.title("Personalized English Vocab App")

    # Simple session
    if "username" not in st.session_state:
        st.session_state["username"] = None

    # --- Auth ---
    if not st.session_state["username"]:
        st.sidebar.header("Login / Register")
        action = st.sidebar.selectbox("Action", ["Login", "Register"])
        with st.sidebar.form("auth_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Submit")
            if submitted:
                conn = get_pg_conn()
                if action == "Login":
                    ok = login_user(conn, username, password)
                    if ok:
                        st.session_state["username"] = username
                        st.success("Logged in as " + username)
                        st.rerun() # force to enter the menu board
                    else:
                        st.error("Invalid credentials")
                else:
                    created = register_user(conn, username, password)
                    if created:
                        st.success("User created. Please login.")
                    else:
                        st.error("Could not create user (maybe exists)")
                conn.close()
        st.stop()

    username = st.session_state["username"]
    st.sidebar.success(f"Signed in: {username}")
    conn = get_pg_conn()
    user = get_user_by_username(conn, username)
    user_id = user['id']

    menu = st.sidebar.radio("Menu", [ "Search / Browse", "Study", "Spaced Review", "My Words", "LLM Passage", "LLM Chunks"])

    if menu == "Search / Browse":
        st.header("Browse Vocabulary")
        
        # 🔎 Search input
        q = st.text_input("Search word or syllable (leave blank to show top by rank)")
        
        # ⚙️ Filter options
        with st.expander("Filter options"):
            min_rank, max_rank = st.slider("Rank range", 1, 5000, (1, 100))   # adjust max as needed
            syll_filter = st.number_input("Syllables (leave 0 for any)", min_value=0, step=1, value=0)
            limit = st.slider("Max results", 10, 200, 30)
        
        filter_key = (q.strip(), min_rank, max_rank, syll_filter, limit)

        if "last_filter" not in st.session_state or st.session_state.last_filter != filter_key:
            st.session_state.rows = search_vocab_for_user(
                conn, user_id,
                query=q if q.strip() else None,
                limit=limit,
                min_rank=None if q.strip() else min_rank,
                max_rank=None if q.strip() else max_rank,
                syll_filter=syll_filter if syll_filter > 0 else None
            )
            st.session_state.last_filter = filter_key

        rows = st.session_state.rows
        
        # 🔍 Apply extra filtering in Python (simpler than rewriting SQL for now)
        filtered_rows = []
        for r in rows:
            wid, word, phon, ex, rank, syll = r
            
            # only apply Python-side rank filter if query is empty
            if not q.strip():
                if rank is None or not (min_rank <= rank <= max_rank):
                    continue
            
            # syllable filter applies in both cases
            if syll_filter != 0 and (not syll or int(syll) != syll_filter):
                continue
            
            filtered_rows.append(r)
        
        # Track which words are already added
        if "added_words" not in st.session_state:
            st.session_state.added_words = set()

        # 📊 Display results
        for r in filtered_rows:
            wid, word, phon, ex, rank, syll = r
            cols = st.columns([1.2, .5, 1.5, 2.5, 1, .5])
            cols[0].write(f"**{word}**")
            cols[1].write(f"**{rank}**")
            cols[2].write(f"`{phon}`" if phon else "")
            cols[3].write(ex or "")

            # ✅ define disabled for this specific word
            disabled = wid in st.session_state.added_words

            if cols[4].button("Add to my list", key=f"add-{wid}", disabled=disabled):
                add_user_vocab(conn, user_id, wid)
                st.session_state.added_words.add(wid)  # mark as added
                st.toast(f"✅ {word} added to your list")
                # st.success(f"Added {word} to your learning list")
            # with cols[5]:
            #     tts_button(word, key=f"tts-{wid}")
            with cols[5]:
                tts_button(word, wid)


    elif menu == "LLM Passage":
        st.header("Generate Passage & Fill-in-the-blanks")
        st.write("Use LLM to create a short passage that includes some target words, and generate a fill-in-blank exercise.")
        target_words = st.text_input("Target words (comma separated) — optional")
        length = st.slider("Length (sentences)", 1, 6, 3)
        num_blanks = st.slider("Number of blanks", 1, 10, 3)   # 👈 new slider
        # Dropdown chọn cấp độ khó
        level = st.selectbox(
            "Select level",
            ["B1 (Easy)", "B2 (Medium)", "C1-C2 (Hard)"]
        )
        if st.button("Generate passage"):
            targets = [t.strip() for t in target_words.split(",") if t.strip()]
            words_length = length * 20
            passage, answers = generate_passage_with_blanks(
                conn, user_id, targets, length=words_length, blanks=num_blanks, level=level
            )

            # Save to session_state
            st.session_state["passage"] = passage
            st.session_state["answers"] = answers
            opts = answers.copy()
            random.shuffle(opts)
            st.session_state["options"] = opts

        # If passage exists, show it
        if "passage" in st.session_state:
            st.write("### Passage")
            st.write(st.session_state["passage"])

            st.write("### Options (shuffled)")
            st.write(", ".join(st.session_state["options"]))

            st.write("### Fill in the blanks")
            for i, correct_word in enumerate(st.session_state["answers"]):
                ans = st.selectbox(
                    f"Blank {i+1}",
                    [""] + st.session_state["options"],
                    key=f"blank-{i}"
                )

                # Show result immediately after selection
                if ans:  # only check if user picked something
                    if ans.strip().lower() == correct_word.lower():
                        st.success("Correct")
                    else:
                        st.error(f"Not correct. Expected: {correct_word}")

    elif menu == "Study":
        st.header("Study - practice words")
        due = get_due_for_user(conn, user_id, limit=10)
        st.write("Words due for practice:")
        if not due:
            st.info("No words due now. Add words in Browse or My Words.")
        for row in due:
            uid, v_id, word, phon, example, rep_count, appearances = row
            st.subheader(word)
            # tts_player(word)
            st.write(f"Phonetic: `{phon}`")
            st.write("Example:", example)
            st.write(f"Repetition count: {rep_count}, appearances: {appearances}")
            sentence = st.text_area(f"Write a sentence using '{word}'", key=f"sent-{v_id}")
            if st.button("Ask LLM to correct", key=f"corr-{v_id}"):
                if sentence.strip() == "":
                    st.warning("Write a sentence first")
                else:
                    corrected = correct_sentence_with_llm(sentence)
                    st.write("**Corrected sentence:**")
                    st.write(corrected)
            if st.button("Mark as seen (increase repetition)", key=f"seen-{v_id}"):
                schedule_next_repetition(conn, user_id, v_id, success=True)
                st.success("Marked. Will appear again according to schedule.")
            if st.button("Mark as known", key=f"known-{v_id}"):
                mark_word_confirmation(conn, user_id, v_id)
                st.success("Great — saved as learned.")

    elif menu == "Spaced Review":
        st.header("Spaced Repetition Settings / Status")
        st.write("This shows your learning list and schedule.")
        cur = conn.cursor()
        cur.execute("""
            SELECT uv.id, v.word, uv.repetition_count, uv.next_due, uv.learned, uv.appearances
            FROM user_vocab uv JOIN words v ON uv.word_id = v.id
            WHERE uv.user_id = %s
            ORDER BY uv.next_due IS NOT NULL, uv.next_due
        """, (user_id,))
        res = cur.fetchall()
        for r in res:
            uid, w, rep, next_due, confirmed, app = r
            st.write(f"- **{w}** — reps: {rep}, next: {next_due}, appearances: {app}, learned: {bool(confirmed)}")
    
    
    elif menu == "My Words":
        st.header("My Words (your personal list)")
        cur = conn.cursor()
        cur.execute("""
            SELECT v.id, v.word, v.phonetic, v.example, uv.repetition_count, uv.learned
            FROM user_vocab uv JOIN words v ON uv.word_id = v.id
            WHERE uv.user_id = %s
            ORDER BY uv.appearances DESC
        """, (user_id,))
        res = cur.fetchall()
        for i, r in enumerate(res):
            vid, w, p, ex, rep, learned = r
            cols = st.columns([2,1,1,1])
            cols[0].write(f"**{w}** — `{p}`")
            cols[0].write(ex or "")
            
            if cols[1].button("Practice now", key=f"p-{vid}-{i}"):
                add_user_vocab(conn, user_id, vid)  # ensure exists
                schedule_next_repetition(conn, user_id, vid, success=False)
                st.info("Scheduled for practice soon.")
                
            if cols[2].button("Mark learned", key=f"ml-{vid}-{i}"):
                mark_word_confirmation(conn, user_id, vid)
                st.success("Marked as learned.")
                
            if learned:
                cols[3].write("✅ Learned")
            else:
                cols[3].write("")


    # elif menu == "LLM Chunks":
    #     st.header("Generate Passage with English Chunks")
    #     st.write("Use LLM to create a natural passage with highlighted English chunks.")
    #     cursor = conn.cursor()

    #     topic = st.text_input("Enter a topic (e.g., Travel, Work, Daily Life):", "Daily life")
    #     length = st.slider("Length (words)", 50, 200, 80)

    #     # Generate passage
    #     if st.button("Generate passage with chunks"):
    #         passage, chunks = generate_passage_with_chunks(topic, length)
    #         st.session_state["chunk_passage"] = passage
    #         st.session_state["chunk_topic"] = topic
    #         st.session_state["chunks"] = chunks

    #         # st.write("### Passage")
    #         # st.markdown(passage)
    #         # tts_button("Read Passage", passage, key="passage-tts")

    #         # st.write("### Extracted Chunks")
    #         # # for c in chunks:
    #         # #     st.write(f"- **{c}**")
    #         # for i, c in enumerate(chunks):
    #         #     col1, col2 = st.columns([4,1])
    #         #     col1.write(f"- **{c}**")
    #         #     with col2:
    #         #         tts_button("Read", c, key=f"chunk-tts-{i}")
        
    #     # Hiển thị nếu đã có trong session_state
    #     if "chunk_passage" in st.session_state:
    #         st.write("### Passage")
    #         st.markdown(st.session_state["chunk_passage"])
    #         # tts_button("Read Passage", st.session_state["chunk_passage"], key="passage-tts")
    #         tts_chunk_button("Read Passage", st.session_state["chunk_passage"], key="passage-tts")

    #     if "chunks" in st.session_state:
    #         st.write("### Extracted Chunks")
    #         for i, c in enumerate(st.session_state["chunks"]):
    #             col1, col2 = st.columns([4,1])
    #             col1.write(f"- **{c}**")
    #             with col2:
    #                 tts_chunk_button("Read", c, key=f"chunk-tts-{i}")

    #     # Save to DB using the helper function
    #     if "chunk_passage" in st.session_state and st.button("Save Chunks"):
    #         save_chunks_for_user(
    #             conn,
    #             user_id,
    #             st.session_state["chunk_topic"],
    #             st.session_state["chunks"]
    #         )
    #         st.success("Chunks saved to database!")

    #     cursor.execute(
    #         "SELECT DISTINCT topic FROM chunks WHERE user_id=%s ORDER BY topic",
    #         (user_id,)
    #     )
    #     topics = [row[0] for row in cursor.fetchall()]

    #     # 2️⃣ Let user select a topic first
    #     selected_topic = st.selectbox(
    #         "Select or type a topic",
    #         options=topics if topics else ["(No topics)"]
    #     )

    #     # 3️⃣ Show chunks ONLY after checkbox is ticked
    #     if st.checkbox("Show saved chunks for selected topic"):
    #         if topics:  # only query if topics exist
    #             cursor.execute(
    #                 "SELECT chunk FROM chunks WHERE user_id=%s AND topic=%s ORDER BY created_at DESC",
    #                 (user_id, selected_topic)
    #             )
    #             rows = cursor.fetchall()
    #             if rows:
    #                 for row in rows:
    #                     st.write(f"**{row[0]}**")
    #             else:
    #                 st.info("No chunks found for this topic.")
    elif menu == "LLM Chunks":
        st.header("Generate Passage with English Chunks")
        st.write("Use LLM to create a natural passage with highlighted English chunks.")
        cursor = conn.cursor()

        # Form để nhập topic và length
        with st.form("chunk_form"):
            topic = st.text_input("Enter a topic (e.g., Travel, Work, Daily Life):", "Daily life")
            length = st.slider("Length (words)", 50, 200, 80)
            submitted = st.form_submit_button("Generate passage with chunks")

        # Nếu generate → gọi LLM và lưu vào session_state
        if submitted:
            passage, chunks = generate_passage_with_chunks(topic, length)
            st.session_state["chunk_passage"] = passage
            st.session_state["chunk_topic"] = topic
            st.session_state["chunks"] = chunks

        # Hiển thị passage nếu đã có
        if "chunk_passage" in st.session_state:
            st.write("### Passage")
            st.markdown(st.session_state["chunk_passage"])
            tts_passage_button(st.session_state["chunk_passage"], key="Passage")

        # Hiển thị chunks nếu đã có
        if "chunks" in st.session_state:
            st.write("### Extracted Chunks")
            for i, c in enumerate(st.session_state["chunks"]):
                col1, col2 = st.columns([4, 1])
                col1.write(f"- **{c}**")
                with col2:
                    tts_chunk_button(c, key=f"chunk{i}")

        # Save to DB
        if "chunk_passage" in st.session_state and st.button("Save Chunks"):
            save_chunks_for_user(
                conn,
                user_id,
                st.session_state["chunk_topic"],
                st.session_state["chunks"]
            )
            st.success("Chunks saved to database!")

        # Show topics from DB
        cursor.execute(
            "SELECT DISTINCT topic FROM chunks WHERE user_id=%s ORDER BY topic",
            (user_id,)
        )
        topics = [row[0] for row in cursor.fetchall()]

        selected_topic = st.selectbox(
            "### Select or type a topic for search",
            options=topics if topics else ["(No topics)"]
        )

        if st.checkbox("Show saved chunks for selected topic"):
            if topics:
                cursor.execute(
                    "SELECT chunk FROM chunks WHERE user_id=%s AND topic=%s ORDER BY created_at DESC",
                    (user_id, selected_topic)
                )
                rows = cursor.fetchall()
                if rows:
                    for row in rows:
                        st.write(f"**{row[0]}**")
                else:
                    st.info("No chunks found for this topic.")


    conn.close()

if __name__ == "__main__":
    main()

