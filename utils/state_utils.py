import streamlit as st

def init_state():
    if 'learned' not in st.session_state:
        st.session_state['learned'] = set()

def add_learned(words):
    for w in words:
        st.session_state['learned'].add(w)

def get_learned():
    return st.session_state['learned']
