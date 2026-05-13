import streamlit as st
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

API_URL = "https://staging-la-model-proofreadorchestrator.languageacademy.com.au/score/essay"
REMARK_URL = "https://la-model-proofreading-staging.languageacademy.com.au/essay-remark"
TOKEN = "pte_lsahdpasdhfasdhfasuaosiudfg"

st.set_page_config(page_title="Essay Evaluator", layout="wide")
st.title("✍️ Essay Evaluation")

essay_prompt = st.text_area("Essay Prompt", height=150)
essay_text = st.text_area("Essay Text", height=300)


def build_highlighted_html(original_text, grammar_errors, mechanics_errors, spelling_errors, extra_space_errors, diffs):
    all_spans = []

    for error in grammar_errors:
        span = error.get("span")
        if span and span.get("start") is not None and span.get("end") is not None and span["start"] <= span["end"]:
            all_spans.append({"start": span["start"], "end": span["end"], "type": "grammar",
                               "message": error.get("message", "Grammar issue"), "suggestion": error.get("corrected", "")})

    for error in mechanics_errors:
        if isinstance(error, dict) and error.get("span"):
            span = error["span"]
            if span["start"] <= span["end"]:
                all_spans.append({"start": span["start"], "end": span["end"], "type": "grammar",
                                   "message": error.get("message", "Mechanics issue"), "suggestion": error.get("corrected", "")})

    for w in spelling_errors:
        span = w.get("span")
        if span and span.get("start") < span.get("end"):
            all_spans.append({"start": span["start"], "end": span["end"], "type": "spelling",
                               "message": "Spelling error", "suggestion": w.get("corrected", "")})

    for error in extra_space_errors:
        span = error.get("span")
        if span and span.get("start") < span.get("end"):
            all_spans.append({"start": span["start"], "end": span["end"], "type": "spacing",
                               "message": "Extra space", "suggestion": error.get("corrected", "")})

    grammar_spelling_spans = {i for sp in all_spans for i in range(sp["start"], sp["end"])}

    for diff in diffs:
        orig_span = diff.get("orig_span")
        if not orig_span or orig_span[0] >= orig_span[1]:
            continue
        start, end = orig_span
        if any(i in grammar_spelling_spans for i in range(start, end)):
            continue
        corrected = diff.get("corrected", "").strip()
        if corrected:
            all_spans.append({"start": start, "end": end, "type": "vocabulary",
                               "message": "Style suggestion", "suggestion": corrected})

    all_spans.sort(key=lambda x: (x["start"], -(x["end"] - x["start"])))
    filtered, covered = [], set()
    for sp in all_spans:
        if any(i in covered for i in range(sp["start"], sp["end"])):
            continue
        filtered.append(sp)
        covered.update(range(sp["start"], sp["end"]))

    filtered.sort(key=lambda x: x["start"], reverse=True)
    html = original_text

    for sp in filtered:
        text_chunk = original_text[sp["start"]:sp["end"]]
        if sp["type"] == "grammar":
            border, bg = "3px solid red", "transparent"
        elif sp["type"] == "spelling":
            border, bg = "3px solid #ff9800", "transparent"
        elif sp["type"] == "spacing":
            border, bg = "3px solid #9c27b0", "transparent"
        else:
            border, bg = "none", "#fff2cc"

        suggestion = sp.get("suggestion", "").strip()
        message = sp.get("message", "Error")
        title = (f"{message}\nChange to: {suggestion}" if suggestion else message).replace('"', '&quot;')
        marked = f'<span style="border:{border};padding:2px 4px;border-radius:4px;background:{bg};font-weight:500;" title="{title}">{text_chunk}</span>'
        html = html[:sp["start"]] + marked + html[sp["end"]:]

    return html


def submit_remark(prompt, text, scoring_response, expected_scores, remark):
    payload = {
        "essay_prompt": prompt,
        "essay_text": text,
        "scoring_response": scoring_response,
        "expected_content_score": expected_scores.get("content"),
        "expected_structure_score": expected_scores.get("structure"),
        "expected_linguistic_score": expected_scores.get("linguistic_range"),
        "remark": remark,
        "token": TOKEN
    }
    try:
        r = requests.post(REMARK_URL, json=payload, verify=False)
        r.raise_for_status()
        return r.json().get("id")
    except requests.exceptions.RequestException as e:
        st.error(f"Failed to submit remark: {e}")
        return None


if st.button("Evaluate Essay"):
    if not essay_prompt.strip() or not essay_text.strip():
        st.warning("Essay prompt and essay text are required.")
    else:
        with st.spinner("Evaluating essay..."):
            resp = requests.post(API_URL, json={"essay_prompt": essay_prompt, "essay_text": essay_text,
                                                "token": TOKEN}, verify=False)
        if not resp.ok:
            st.error(f"API Error: {resp.status_code} - {resp.text}")
            st.stop()

        st.session_state["essay_result"] = resp.json()
        st.session_state["essay_prompt"] = essay_prompt
        st.session_state["essay_text"] = essay_text
        st.session_state["remark_submitted"] = False
        st.session_state["remark_id"] = None

if st.session_state.get("essay_result"):
    data = st.session_state["essay_result"]
    services = data["services"]
    lang = services["language"]
    essay_eval = services["essay_evaluation"]
    form = services["form"]

    st.divider()

    html = build_highlighted_html(
        lang.get("original", st.session_state["essay_text"]),
        lang.get("grammar_errors", []),
        lang.get("mechanics_errors", []),
        lang.get("spelling_errors", []),
        lang.get("extra_space_errors", []),
        lang.get("diffs", [])
    )
    st.markdown(f"<div style='font-size:16px;line-height:1.8;padding:1rem;border:1px solid #e0e0e0;border-radius:8px'>{html}</div>", unsafe_allow_html=True)

    st.divider()

    ee = essay_eval
    lang_scores = lang.get("scores", {})
    error_counts = lang.get("error_counts", {})

    def from_errors(count, max_score):
        return max(0, max_score - count * 0.5)

    def get_score(ee_key, lang_key=None, fallback_count=0, max_score=2):
        v = ee.get(ee_key)
        if v is not None: return v
        if lang_key:
            v = lang_scores.get(lang_key)
            if v is not None: return min(v, max_score)
        return from_errors(fallback_count, max_score)

    grammar_score  = get_score("grammar_score",  "grammar",  error_counts.get("grammar", 0) + error_counts.get("spacing", 0), max_score=2)
    spelling_score = get_score("spelling_score", "spelling", error_counts.get("spelling", 0), max_score=2)
    vocab_score    = get_score("vocabulary_score", "vocabulary", error_counts.get("vocabulary", 0), max_score=2)

    rows = [
        ("Content",         ee.get("content_score"),          "/6", ee.get("content_feedback")),
        ("Form",            ee.get("form_score",  form.get("score")), "/2", ee.get("form_feedback", form.get("feedback"))),
        ("Grammar",         grammar_score,                    "/2", ee.get("grammar_feedback")),
        ("Vocabulary",      vocab_score,                      "/2", ee.get("vocabulary_feedback", lang.get("vocabulary", {}).get("feedback"))),
        ("Linguistic range",ee.get("linguistic_range_score", ee.get("linguistic_score")), "/6", ee.get("linguistic_range_feedback", ee.get("linguistic_feedback"))),
        ("Structure",       ee.get("structure_score"),        "/6", ee.get("structure_feedback")),
        ("Spelling",        spelling_score,                   "/2", ee.get("spelling_feedback")),
    ]

    total = ee.get("total_score")
    if total is None:
        total = sum(r[1] for r in rows if r[1] is not None)

    for label, score, denom, feedback in rows:
        c1, c2 = st.columns([1, 4])
        c1.metric(label, f"{score}{denom}" if score is not None else "—")
        if feedback:
            c2.info(feedback)

    st.divider()
    st.metric("Total", f"{total}/26")

    st.divider()
    st.markdown("### 📬 Submit Feedback")
    st.markdown("If you think the scores should be different, enter expected scores and a remark.")

    rc1, rc2, rc3 = st.columns(3)
    exp_content   = rc1.number_input("Content",    0, 6, int(rows[0][1] or 0), key="exp_content")
    exp_structure = rc2.number_input("Structure",  0, 6, int(rows[5][1] or 0), key="exp_structure")
    exp_ling      = rc3.number_input("Linguistic", 0, 6, int(rows[4][1] or 0), key="exp_ling")

    remark = st.text_area("Remark", placeholder="Explain why the scores should be different...")

    if not st.session_state.get("remark_submitted"):
        if st.button("📤 Submit Feedback"):
            expected_scores = {
                "content": exp_content,
                "structure": exp_structure,
                "linguistic_range": exp_ling,
            }
            inserted_id = submit_remark(
                st.session_state["essay_prompt"],
                st.session_state["essay_text"],
                st.session_state["essay_result"],
                expected_scores, remark
            )
            if inserted_id:
                st.session_state["remark_submitted"] = True
                st.session_state["remark_id"] = inserted_id
                st.rerun()
    else:
        st.success(f"Feedback submitted! ID: {st.session_state.get('remark_id')}")
