import streamlit as st
import requests
import urllib3
from difflib import SequenceMatcher

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

API_URL = "https://la-model-proofread.languageacademy.com.au/correct-text"
TOKEN = "pte_lsahdpasdhfasdhfasuaosiudfg"

st.set_page_config(page_title="Grammar Corrector", layout="wide", page_icon="✏️")

st.markdown("""
<style>
.correction-box { background-color: #f8f9fa; border-radius: 10px; padding: 1rem; border-left: 4px solid #28a745; }
.original-box   { background-color: #fff3cd; border-radius: 10px; padding: 1rem; border-left: 4px solid #ffc107; }
.stats-card     { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 1rem; border-radius: 10px; text-align: center; margin: 0.5rem 0; }
</style>
""", unsafe_allow_html=True)

st.title("✏️ Grammar Corrector")

text = st.text_area("Enter Your Text", height=200, placeholder="Type or paste your text here...")

col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    correct_button = st.button("🚀 Correct My Text", type="primary", use_container_width=True)

if correct_button:
    if not text.strip():
        st.warning("⚠️ Please enter some text to correct.")
    else:
        with st.spinner("Analyzing..."):
            resp = requests.post(
                API_URL,
                json={"text": text, "token": TOKEN},
                verify=False
            )
            data = resp.json()

        original_text = data["original_text"]
        corrected_text = data["corrected_text"]
        changes_made = original_text != corrected_text
        similarity = SequenceMatcher(None, original_text, corrected_text).ratio()

        st.divider()

        col1, col2, col3, col4 = st.columns(4)
        col1.markdown(f'<div class="stats-card"><h3>{len(original_text.split())}</h3><p>Words</p></div>', unsafe_allow_html=True)
        col2.markdown(f'<div class="stats-card"><h3>{len(original_text)}</h3><p>Characters</p></div>', unsafe_allow_html=True)
        col3.markdown(f'<div class="stats-card"><h3>{"Yes" if changes_made else "No"}</h3><p>Changes Made</p></div>', unsafe_allow_html=True)
        col4.markdown(f'<div class="stats-card"><h3>{similarity*100:.1f}%</h3><p>Similarity</p></div>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### 📄 Original Text")
            st.markdown(f'<div class="original-box">{original_text}</div>', unsafe_allow_html=True)
        with col2:
            st.markdown("#### ✅ Corrected Text")
            st.markdown(f'<div class="correction-box">{corrected_text}</div>', unsafe_allow_html=True)

        if changes_made:
            st.markdown("#### 📋 Copy Corrected Text")
            st.code(corrected_text, language=None)

            with st.expander("🔍 See Detailed Changes"):
                matcher = SequenceMatcher(None, original_text, corrected_text)
                diff_html = ""
                for tag, i1, i2, j1, j2 in matcher.get_opcodes():
                    if tag == "equal":
                        diff_html += original_text[i1:i2]
                    elif tag == "delete":
                        diff_html += f'<span style="background-color:#ffcccc;text-decoration:line-through">{original_text[i1:i2]}</span>'
                    elif tag == "insert":
                        diff_html += f'<span style="background-color:#ccffcc">{corrected_text[j1:j2]}</span>'
                    elif tag == "replace":
                        diff_html += f'<span style="background-color:#ffcccc;text-decoration:line-through">{original_text[i1:i2]}</span>'
                        diff_html += f'<span style="background-color:#ccffcc">{corrected_text[j1:j2]}</span>'
                st.markdown(f'<div style="padding:1rem;border:1px solid #ddd;border-radius:5px;font-family:monospace">{diff_html}</div>', unsafe_allow_html=True)
                st.markdown("**Legend:** <span style='background-color:#ffcccc'>Removed</span> | <span style='background-color:#ccffcc'>Added</span>", unsafe_allow_html=True)

        with st.expander("🔍 Raw JSON"):
            st.json(data)
