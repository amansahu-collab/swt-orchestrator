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
    """Enhanced highlighting with better tooltips and error handling"""
    all_spans = []

    # Grammar errors
    for error in grammar_errors:
        span = error.get("span")
        if span and span.get("start") is not None and span.get("end") is not None:
            if span["start"] <= span["end"]:  # Include empty spans (insertions)
                all_spans.append({
                    "start": span["start"],
                    "end": span["end"],
                    "type": "grammar",
                    "message": error.get("message", error.get("type", "Grammar issue")),
                    "suggestion": error.get("corrected", ""),
                    "original": original_text[span["start"]:span["end"]]
                })

    # Mechanics errors (treat as grammar)
    for error in mechanics_errors:
        if isinstance(error, dict) and error.get("span"):
            span = error.get("span")
            if span["start"] < span["end"]:
                all_spans.append({
                    "start": span["start"],
                    "end": span["end"],
                    "type": "grammar",
                    "message": error.get("message", error.get("type", "Mechanics issue")),
                    "suggestion": error.get("suggestion", ""),
                    "original": original_text[span["start"]:span["end"]]
                })

    # Spelling errors
    for word_info in spelling_errors:
        span = word_info.get("span")
        if span and span.get("start") < span.get("end"):
            all_spans.append({
                "start": span["start"],
                "end": span["end"],
                "type": "spelling",
                "message": "Spelling error",
                "suggestion": word_info.get("corrected", ""),
                "original": word_info.get("original", original_text[span["start"]:span["end"]])
            })

    # Track covered positions
    grammar_spelling_spans = set()
    for sp in all_spans:
        for i in range(sp["start"], sp["end"]):
            grammar_spelling_spans.add(i)

    # LLM diffs (vocabulary/style suggestions)
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
            "type": "vocabulary",
            "message": "Style suggestion",
            "suggestion": corrected,
            "original": original_text[start:end]
        })

    # Remove overlapping spans (prioritize by type and length)
    all_spans.sort(key=lambda x: (x["start"], -(x["end"] - x["start"])))
    filtered = []
    covered = set()

    for sp in all_spans:
        if any(i in covered for i in range(sp["start"], sp["end"])):
            continue
        filtered.append(sp)
        for i in range(sp["start"], sp["end"]):
            covered.add(i)

    # Apply highlighting (reverse order to maintain indices)
    filtered.sort(key=lambda x: x["start"], reverse=True)
    html = original_text

    for sp in filtered:
        # Handle empty spans (insertions)
        if sp["start"] == sp["end"]:
            text_chunk = ""
            marker = f'<span style="background:#ffd6d6; padding:2px 4px; border-radius:4px; border-bottom:2px solid red; color:red;" title="{sp.get("suggestion", sp["message"])}" style="cursor:help;">⇧{sp.get("suggestion", "")}</span>'
            html = html[:sp["start"]] + marker + html[sp["start"]:]
            continue

        text_chunk = original_text[sp["start"]:sp["end"]]

        # Color coding
        if sp["type"] == "grammar":
            color = "red"
            bg = "#ffd6d6"
        elif sp["type"] == "spelling":
            color = "#ff9800"
            bg = "#ffe6cc"
        else:  # vocabulary
            color = "#555"
            bg = "#fff2cc"

        # Build tooltip
        title = sp["suggestion"] if sp.get("suggestion") else sp["message"]
        title = title.replace('"', '&quot;')  # Escape quotes

        marked = (
            f'<span style="background:{bg}; padding:2px 4px;'
            f'border-radius:4px; border-bottom:2px solid {color};" '
            f'title="{title}">{text_chunk}</span>'
        )

        html = html[:sp["start"]] + marked + html[sp["end"]:]

    return html, filtered


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
        form = services["form"]
        content = services["content"]
        lang = services["language"]

        st.divider()

        # -----------------------------
        # Form Evaluation
        # -----------------------------
        st.subheader("📋 Form Evaluation")
        
        col1, col2 = st.columns([1, 3])
        col1.metric("Form Score", form["score"])
        col2.info(form["feedback"])

        st.divider()

        # -----------------------------
        # Content Evaluation
        # -----------------------------
        st.subheader("📘 Content Evaluation")

        c1, c2, c3 = st.columns(3)
        c1.metric("Content Coverage", f"{content.get('content_percentage', 0)}%")
        c2.metric("Score", content.get("score", 0))
        c3.metric("Relevance", content.get("relevance_level", "unknown").title())

        st.markdown("**Covered Ideas**")
        for i in content.get("covered_ideas", []):
            st.success(i)

        st.markdown("**Missing Ideas**")
        for i in content.get("missing_ideas", []):
            st.error(i)

        st.info(content.get("feedback", "No feedback available"))

        st.divider()

        # -----------------------------
        # Language Evaluation
        # -----------------------------
        st.subheader("✍️ Language Evaluation")

        col1, col2 = st.columns([2, 1])

        with col1:
            st.subheader("📄 Summary (Highlighted)")

            html, all_errors = build_highlighted_html(
                lang.get("original", summary),
                lang.get("grammar_errors", []),
                lang.get("mechanics_errors", []),
                lang.get("spelling_errors", []),
                lang.get("diffs", [])
            )

            st.markdown(
                f"<div style='font-size:16px;line-height:1.6'>{html}</div>",
                unsafe_allow_html=True
            )

            if lang.get("corrected"):
                st.subheader("✅ Corrected Summary")
                st.info(lang["corrected"])

        with col2:
            st.subheader("📊 Language Scores")
            
            scores = lang.get("scores", {})
            s1, s2, s3 = st.columns(3)
            s1.metric("Grammar", f"{scores.get('grammar', 0)}%")
            s2.metric("Spelling", f"{scores.get('spelling', 0)}%")
            s3.metric("Vocabulary", f"{scores.get('vocabulary', 0)}%")

            # Error counts
            grammar_count = len(lang.get('grammar_errors', [])) + len(lang.get('mechanics_errors', []))
            spelling_count = len(lang.get('spelling_errors', []))
            vocab_count = len(lang.get('diffs', []))
            
            st.markdown("### Error Counts")
            st.write(f"🔴 Grammar: {grammar_count}")
            st.write(f"🟠 Spelling: {spelling_count}")
            st.write(f"🟡 Vocabulary: {vocab_count}")
            st.write(f"**Total: {grammar_count + spelling_count + vocab_count}**")

            # Error details in expandable sections
            if grammar_count > 0:
                with st.expander(f"Grammar Errors ({grammar_count})"):
                    for e in lang.get("grammar_errors", []):
                        orig = e.get("original", "")
                        sug = e.get("corrected", "")
                        if orig is not None and sug is not None:
                            st.write(f"• '{orig}' → '{sug}'")
                        else:
                            st.write(f"• {e.get('message', e.get('type', 'Grammar issue'))}")
                    
                    for m in lang.get("mechanics_errors", []):
                        if isinstance(m, dict):
                            orig = lang.get("original", summary)[m.get("span", {}).get("start", 0):m.get("span", {}).get("end", 0)] if m.get("span") else ""
                            sug = m.get("suggestion", "")
                            if orig and sug:
                                st.write(f"• '{orig}' → '{sug}'")
                            else:
                                st.write(f"• {m.get('message', m.get('type', 'Mechanics issue'))}")
            
            if spelling_count > 0:
                with st.expander(f"Spelling Errors ({spelling_count})"):
                    for w in lang.get("spelling_errors", []):
                        orig = w.get("original", "")
                        sug = w.get("corrected", "")
                        if orig and sug and sug != orig:
                            st.write(f"• '{orig}' → '{sug}'")
                        else:
                            st.write(f"• {orig}")
            
            if vocab_count > 0:
                with st.expander(f"Vocabulary Suggestions ({vocab_count})"):
                    for diff in lang.get("diffs", []):
                        orig_span = diff.get("orig_span")
                        if orig_span:
                            orig = lang.get("original", summary)[orig_span[0]:orig_span[1]]
                            sug = diff.get("corrected", "")
                            if orig and sug:
                                st.write(f"• '{orig}' → '{sug}'")

            # Vocabulary insights
            vocab_data = lang.get("vocabulary", {})
            if vocab_data.get("insights"):
                st.markdown("### Vocabulary Feedback")
                for insight in vocab_data["insights"]:
                    st.info(insight)

        # Raw JSON view
        with st.expander("🔍 Raw JSON Response"):
            st.json(data)

        with st.expander("🔍 Raw JSON"):
            st.json(data)
