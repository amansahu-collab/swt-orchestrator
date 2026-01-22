import streamlit as st
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

API_URL = "https://la-model-proofreadorchestrator.languageacademy.com.au/score"

st.set_page_config(page_title="Writing Evaluator", layout="wide")
st.title("📝 Writing Evaluation Orchestrator")

# -----------------------------
# Inputs
# -----------------------------
passage = st.text_area(
    "Enter Passage (Original text)",
    height=220,
    placeholder="Paste passage here..."
)

summary = st.text_area(
    "Enter Student Summary",
    height=180,
    placeholder="Paste summary here..."
)

# -----------------------------
# Highlighting function
# -----------------------------
def build_highlighted_html(original_text, grammar_errors, mechanics_errors, spelling_errors, diffs):
    all_spans = []

    for error in grammar_errors:
        span = error.get("span")
        if span and span.get("start") is not None and span.get("end") is not None:
            if span["start"] < span["end"]:
                all_spans.append({
                    "start": span["start"],
                    "end": span["end"],
                    "type": "grammar",
                    "message": error.get("message", error.get("type", "")),
                    "suggestion": error.get("suggestion", "")
                })

    for error in mechanics_errors:
        if isinstance(error, dict) and error.get("span"):
            span = error.get("span")
            if span["start"] < span["end"]:
                all_spans.append({
                    "start": span["start"],
                    "end": span["end"],
                    "type": "grammar",
                    "message": error.get("message", error.get("type", "")),
                    "suggestion": error.get("suggestion", "")
                })

    for word_info in spelling_errors:
        span = word_info.get("span")
        if span and span.get("start") < span.get("end"):
            all_spans.append({
                "start": span["start"],
                "end": span["end"],
                "type": "spelling",
                "message": f"Spelling: {word_info.get('word','')}",
                "suggestion": word_info.get("suggestion", "")
            })

    grammar_spelling_spans = set()
    for sp in all_spans:
        for i in range(sp["start"], sp["end"]):
            grammar_spelling_spans.add(i)

    for diff in diffs:
        orig_span = diff.get("orig_span")
        if not orig_span or orig_span[0] >= orig_span[1]:
            continue
        start, end = orig_span
        if any(i in grammar_spelling_spans for i in range(start, end)):
            continue
        corrected = diff.get("corrected", "").strip()
        if not corrected:
            continue
        all_spans.append({
            "start": start,
            "end": end,
            "type": "llm_diff",
            "message": f"Suggestion",
            "suggestion": corrected
        })

    all_spans.sort(key=lambda x: (x["start"], -(x["end"] - x["start"])))
    filtered = []
    covered = set()

    for sp in all_spans:
        if any(i in covered for i in range(sp["start"], sp["end"])):
            continue
        filtered.append(sp)
        for i in range(sp["start"], sp["end"]):
            covered.add(i)

    filtered.sort(key=lambda x: x["start"], reverse=True)
    html = original_text

    for sp in filtered:
        text_chunk = original_text[sp["start"]:sp["end"]]

        if sp["type"] == "grammar":
            style = "background:#ffd6d6;padding:2px 4px;border-radius:4px;border-bottom:2px solid red;"
        elif sp["type"] == "spelling":
            style = "background:#ffe6cc;padding:2px 4px;border-radius:4px;border-bottom:2px solid #ff9800;"
        else:
            style = "background:#fff2cc;padding:2px 4px;border-radius:4px;border-bottom:2px dotted #555;"

        title = sp["message"]
        if sp.get("suggestion"):
            title += f" → {sp['suggestion']}"

        html = (
            html[:sp["start"]] +
            f"<span style='{style}' title='{title}'>{text_chunk}</span>" +
            html[sp["end"]:]
        )

    return html


# -----------------------------
# Evaluate
# -----------------------------
if st.button("Evaluate Writing"):
    if not passage.strip() or not summary.strip():
        st.warning("Passage and summary are required.")
    else:
        with st.spinner("Running orchestrator..."):
            resp = requests.post(
                API_URL,
                json={
                    "test_type": "summarize_written_text",
                    "passage": passage,
                    "summary": summary,
                    "token": "pte_lsahdpasdhfasdhfasuaosiudfg"
                },
                verify=False
            )
            data = resp.json()

        services = data["services"]
        content = services["content"]
        lang = services["language"]

        st.divider()

        # -----------------------------
        # Content Evaluation
        # -----------------------------
        st.subheader("📘 Content Evaluation")

        c1, c2, c3 = st.columns(3)
        c1.metric("Content Coverage", f"{content['content_percentage']}%")
        c2.metric("Score", content["score"])
        c3.metric("Relevance", content["relevance_level"].title())

        st.markdown("**Covered Ideas**")
        for i in content["covered_ideas"]:
            st.success(i)

        st.markdown("**Missing Ideas**")
        for i in content["missing_ideas"]:
            st.error(i)

        st.info(content["feedback"])

        st.divider()

        # -----------------------------
        # Language Evaluation
        # -----------------------------
        st.subheader("✍️ Language Evaluation")

        col1, col2 = st.columns([2, 1])

        with col1:
            st.markdown("**Highlighted Summary**")

            html = build_highlighted_html(
                lang["original"],
                lang["grammar_errors"],
                lang["mechanics_errors"],
                lang["spelling"]["misspelled_words"],
                lang["diffs"]
            )

            st.markdown(
                f"<div style='font-size:16px;line-height:1.6'>{html}</div>",
                unsafe_allow_html=True
            )

            st.markdown("**Corrected Version**")
            st.success(lang["corrected"])

        with col2:
            s1, s2, s3 = st.columns(3)
            s1.metric("Grammar", f"{lang['scores']['grammar']}%")
            s2.metric("Spelling", f"{lang['scores']['spelling']}%")
            s3.metric("Vocabulary", f"{lang['scores']['vocabulary']}%")

            st.markdown("### Vocabulary Insights")
            for i in lang["vocabulary"]["insights"]:
                st.info(i)

            st.markdown("### Grammar Errors")
            if lang["grammar_errors"]:
                for e in lang["grammar_errors"]:
                    msg = e.get("message", e.get("type"))
                    sug = e.get("suggestion", "")
                    if sug:
                        st.error(f"{msg} → {sug}")
                    else:
                        st.error(msg)
            else:
                st.success("No grammar errors")

            st.markdown("### Mechanics")
            if lang["mechanics_errors"]:
                for m in lang["mechanics_errors"]:
                    if isinstance(m, dict):
                        msg = m.get("message", m.get("type"))
                        sug = m.get("suggestion", "")
                        if sug:
                            st.warning(f"{msg} → {sug}")
                        else:
                            st.warning(msg)
                    else:
                        st.warning(m)
            else:
                st.success("No mechanics issues")

            st.markdown("### Spelling")
            if lang["spelling"]["misspelled_words"]:
                for w in lang["spelling"]["misspelled_words"]:
                    word = w.get("word", "")
                    sug = w.get("suggestion", "")
                    if sug and sug != word:
                        st.error(f"{word} → {sug}")
                    else:
                        st.error(word)
            else:
                st.success("No spelling mistakes")

        with st.expander("🔍 Raw JSON"):
            st.json(data)
