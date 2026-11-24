from datetime import datetime, timezone

import requests
import streamlit as st
from pymongo import MongoClient

API_URL = "https://staging-la-model-proofreadorchestrator.languageacademy.com.au/score"
TOKEN = "pte_lsahdpasdhfasdhfasuaosiudfg"

MONGO_URI = "mongodb+srv://amansahu_db_user:12121212qwqw@cluster0.4hzwf6o.mongodb.net/"
MONGO_DB = "remark"
MONGO_COLLECTION = "summary_scorer_calls"

st.set_page_config(page_title="Summary Scorer", page_icon="📝", layout="wide")


@st.cache_resource
def _get_mongo_client():
    """Shared MongoClient with public DNS fallbacks for mongodb+srv lookups."""
    try:
        import dns.resolver
        dns.resolver.default_resolver = dns.resolver.Resolver(configure=True)
        existing = list(dns.resolver.default_resolver.nameservers)
        for ns in ("8.8.8.8", "1.1.1.1"):
            if ns not in existing:
                existing.append(ns)
        dns.resolver.default_resolver.nameservers = existing
    except Exception:
        pass
    return MongoClient(MONGO_URI, serverSelectionTimeoutMS=10000)


def get_collection():
    return _get_mongo_client()[MONGO_DB][MONGO_COLLECTION]


def save_call(payload, response):
    """Store input (without token) and output. Returns id string or 'ERROR: ...'."""
    try:
        doc = {
            "created_at": datetime.now(timezone.utc),
            "test_type": payload["test_type"],
            "service_type": payload["service_type"],
            "ideal_summary": payload["ideal_summary"],
            "passage": payload["passage"],
            "summary": payload["summary"],
            "response": response,
        }
        return str(get_collection().insert_one(doc).inserted_id)
    except Exception as e:
        return f"ERROR: {e}"


@st.cache_data(ttl=120, show_spinner=False)
def load_previous_calls(limit):
    calls = []
    for d in get_collection().find().sort("created_at", -1).limit(int(limit)):
        d["_id"] = str(d["_id"])
        calls.append(d)
    return calls


def render_result(data):
    if data.get("errors"):
        st.error(data["errors"])

    services = data.get("services") or {}
    form = services.get("form") or {}
    content = services.get("content") or {}
    lang = services.get("language") or {}

    # Ideas and their coverage come first
    st.header("Ideas & coverage")
    st.write(f"Relevance: **{content.get('relevance_level', '-')}**, "
             f"coverage: **{content.get('content_percentage', '-')}%**")
    points = content.get("key_point_results") or []
    if points:
        st.dataframe(
            [{"id": p.get("id"), "idea": p.get("idea"),
              "status": {"covered": "✅ covered", "uncovered": "❌ uncovered"}.get(
                  p.get("label"), p.get("label")),
              "coverage %": p.get("coverage_percent"), "evidence": p.get("evidence")}
             for p in points],
            use_container_width=True, hide_index=True)
    st.write(content.get("feedback", ""))

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Form", form.get("score", "-"))
    m2.metric("Content", content.get("score", "-"))
    m3.metric("Vocabulary", (lang.get("vocabulary") or {}).get("score", "-"))
    m4.metric("Spelling/Grammar", (lang.get("scores") or {}).get("spelling_grammar_combined", "-"))

    tab_form, tab_lang, tab_raw = st.tabs(["Form", "Language", "Raw JSON"])

    with tab_form:
        st.write(form.get("feedback", ""))
        st.write(f"Word count: {form.get('word_count', '-')}")
        if form.get("issues"):
            st.json(form["issues"])

    with tab_lang:
        st.subheader("Corrected")
        st.write(lang.get("corrected", ""))
        counts = lang.get("error_counts") or {}
        if counts:
            st.write(counts)
        for key, label in [("grammar_errors", "Grammar"), ("spelling_errors", "Spelling"),
                           ("mechanics_errors", "Mechanics"), ("extra_space_errors", "Extra space")]:
            errs = lang.get(key) or []
            if errs:
                st.subheader(label)
                st.dataframe(
                    [{"original": e.get("original"), "corrected": e.get("corrected"),
                      "message": e.get("message"), "start": (e.get("span") or {}).get("start"),
                      "end": (e.get("span") or {}).get("end")} for e in errs],
                    use_container_width=True, hide_index=True)

    with tab_raw:
        st.json(data)


st.title("📝 Summarize Text Scorer")
tab_new, tab_history = st.tabs(["New test", "Previous tests"])

with tab_new:
    with st.form("score_form"):
        c1, c2, c3 = st.columns(3)
        test_type = c1.selectbox("Test type", ["summarize_written_text", "summarize_spoken_text"])
        service_type = c2.selectbox("Service type", ["academic", "core"])
        ideal_summary = c3.checkbox("Ideal summary", value=False)
        passage = st.text_area("Passage", height=250)
        summary = st.text_area("Summary", height=150)
        submitted = st.form_submit_button("Score", type="primary")

    if submitted:
        if not (passage.strip() and summary.strip()):
            st.error("Passage and summary are required.")
        else:
            payload = {
                "test_type": test_type,
                "passage": passage,
                "summary": summary,
                "token": TOKEN,
                "ideal_summary": ideal_summary,
                "service_type": service_type,
            }
            data = None
            try:
                with st.spinner("Scoring..."):
                    resp = requests.post(API_URL, json=payload, timeout=120)
                resp.raise_for_status()
                data = resp.json()
            except requests.RequestException as e:
                st.error(f"Request failed: {e}")
            except ValueError:
                st.error("Response was not valid JSON.")
                st.code(resp.text)

            if data is not None:
                call_id = save_call(payload, data)
                if call_id.startswith("ERROR:"):
                    st.warning(f"Could not save this test to MongoDB: {call_id[7:].strip()}")
                else:
                    load_previous_calls.clear()
                    st.caption(f"Saved to MongoDB ({MONGO_DB}.{MONGO_COLLECTION}), id: {call_id}")
                render_result(data)

with tab_history:
    h1, h2 = st.columns([1, 3])
    limit = h1.number_input("Show latest", min_value=5, max_value=500, value=50, step=5)
    if h2.button("Refresh"):
        load_previous_calls.clear()

    try:
        calls = load_previous_calls(limit)
    except Exception as e:
        calls = []
        st.error(f"Could not load previous tests from MongoDB: {e}")

    if not calls:
        st.info("No previous tests found.")
    else:
        rows = []
        for c in calls:
            ts = c.get("created_at")
            services = (c.get("response") or {}).get("services") or {}
            content = services.get("content") or {}
            rows.append({
                "time (UTC)": ts.strftime("%Y-%m-%d %H:%M") if hasattr(ts, "strftime") else "-",
                "test type": c.get("test_type"),
                "service": c.get("service_type"),
                "content %": content.get("content_percentage"),
                "content score": content.get("score"),
                "form score": (services.get("form") or {}).get("score"),
                "summary": (c.get("summary") or "")[:80],
            })

        st.caption("Click a row to open it.")
        event = st.dataframe(
            rows, use_container_width=True, hide_index=True,
            on_select="rerun", selection_mode="single-row", key="history_table")
        selected = event.selection.rows
        if not selected:
            st.stop()

        call = calls[selected[0]]
        st.divider()
        st.markdown(f"**Test type:** {call.get('test_type')}  \n"
                    f"**Service type:** {call.get('service_type')}  \n"
                    f"**Ideal summary:** {call.get('ideal_summary')}")
        with st.expander("Passage"):
            st.write(call.get("passage", ""))
        with st.expander("Summary", expanded=True):
            st.write(call.get("summary", ""))
        render_result(call.get("response") or {})
