# utils/tts_utils.py
import base64
import io
from gtts import gTTS
import streamlit as st
# import time
import json
import streamlit.components.v1 as components

def tts_button(word: str, wid: int):
    components.html(
        f"""
        <button onclick="speak{wid}()" style="border:none;background:none;cursor:pointer;font-size:18px;">
            🔊
        </button>
        <script>
        function speak{wid}() {{
            var utterance = new SpeechSynthesisUtterance("{word}");
            speechSynthesis.speak(utterance);
        }}
        </script>
        """,
        height=40,
    )

def tts_passage_button(text: str, key: str):
    safe_text = text.replace('"', '\\"').replace("\n", " ")
    components.html(
        f"""
        <button onclick="speak{key}()" style="margin-right:6px;">▶ Read Passage</button>
        <button onclick="pause{key}()" style="margin-right:6px;">⏸ Pause</button>
        <button onclick="stop{key}()">⏹ Stop</button>
        <script>
        var utterance{key};
        function speak{key}() {{
            if (!utterance{key}) {{
                utterance{key} = new SpeechSynthesisUtterance("{safe_text}");
            }}
            speechSynthesis.cancel(); // reset trước
            speechSynthesis.speak(utterance{key});
        }}
        function pause{key}() {{
            if (speechSynthesis.speaking) {{
                if (speechSynthesis.paused) {{
                    speechSynthesis.resume();
                }} else {{
                    speechSynthesis.pause();
                }}
            }}
        }}
        function stop{key}() {{
            speechSynthesis.cancel();
        }}
        </script>
        """,
        height=50,
    )

def tts_chunk_button(text: str, key: str):
    safe_text = text.replace('"', '\\"').replace("\n", " ")
    components.html(
        f"""
        <button onclick="speak{key}()" style="border:none;background:none;cursor:pointer;font-size:14px;">
            🔊 Read
        </button>
        <script>
        function speak{key}() {{
            var utterance = new SpeechSynthesisUtterance("{safe_text}");
            utterance.rate = 1;
            utterance.pitch = 1;
            speechSynthesis.speak(utterance);
        }}
        </script>
        """,
        height=40,
    )
