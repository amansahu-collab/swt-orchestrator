import streamlit as st
from pymongo import MongoClient
import pandas as pd
import plotly.graph_objects as go
from bson import ObjectId

@st.cache_resource
def get_collection():
    client = MongoClient("mongodb+srv://amansahu_db_user:12121212qwqw@cluster0.4hzwf6o.mongodb.net/?appName=Cluster0")
    return client["LA_writing-database"]["essay-remarks"]

@st.cache_data(ttl=300)
def load_data():
    docs = list(get_collection().find())
    records = []
    for doc in docs:
        ee = doc.get("scoring_response", {}).get("services", {}).get("essay_evaluation", {})
        lang = doc.get("scoring_response", {}).get("services", {}).get("language", {})
        form = doc.get("scoring_response", {}).get("services", {}).get("form", {})
        lang_scores = lang.get("scores", {})

        records.append({
            "id": str(doc["_id"]),
            "prompt": doc.get("essay_prompt", "")[:80] + "...",
            "remark": doc.get("remark", ""),
            # model scores
            "content":    ee.get("content_score", 0),
            "structure":  ee.get("structure_score", 0),
            "linguistic": ee.get("linguistic_score", 0),
            "form":       form.get("score", 0),
            "grammar":    lang_scores.get("grammar", 0),
            "vocabulary": lang_scores.get("vocabulary", 0),
            "spelling":   lang_scores.get("spelling", 0),
            # expected scores
            "exp_content":    doc.get("expected_content_score", 0),
            "exp_structure":  doc.get("expected_structure_score", 0),
            "exp_linguistic": doc.get("expected_linguistic_score", 0),
            "exp_form":       doc.get("expected_form_score", 0),
            "exp_grammar":    doc.get("expected_grammar_score", 0),
            "exp_vocabulary": doc.get("expected_vocabulary_score", 0),
            "exp_spelling":   doc.get("expected_spelling_score", 0),
        })

    df = pd.DataFrame(records)
    score_cols = ["content", "structure", "linguistic", "form", "grammar", "vocabulary", "spelling"]
    exp_cols   = ["exp_content", "exp_structure", "exp_linguistic", "exp_form", "exp_grammar", "exp_vocabulary", "exp_spelling"]
    df["total_model"]    = df[score_cols].sum(axis=1)
    df["total_expected"] = df[exp_cols].sum(axis=1)
    df["total_diff"]     = (df["total_model"] - df["total_expected"]).abs()
    return df

SCORE_FIELDS = [
    ("Content",    "content",    "exp_content",    6),
    ("Structure",  "structure",  "exp_structure",  6),
    ("Linguistic", "linguistic", "exp_linguistic",  6),
    ("Form",       "form",       "exp_form",        2),
    ("Grammar",    "grammar",    "exp_grammar",     2),
    ("Vocabulary", "vocabulary", "exp_vocabulary",  2),
    ("Spelling",   "spelling",   "exp_spelling",    2),
]

st.set_page_config(page_title="Essay Scoring Dashboard", layout="wide")
st.title("✍️ Essay Scoring — Model vs Expected")

df = load_data()
if df.empty:
    st.warning("No data found.")
    st.stop()

# ── Sidebar filters ──────────────────────────────────────────────────────────
st.sidebar.header("🔍 Filters")
diff_range = st.sidebar.slider("Total score difference", 0, 26, (0, 26))
filtered = df[(df["total_diff"] >= diff_range[0]) & (df["total_diff"] <= diff_range[1])]
st.sidebar.metric("Showing", len(filtered))

# ── Top metrics ──────────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Records", len(df))
c2.metric("Avg Model Total", f"{df['total_model'].mean():.1f}")
c3.metric("Avg Expected Total", f"{df['total_expected'].mean():.1f}")
c4.metric("Avg Difference", f"{df['total_diff'].mean():.1f}")

st.divider()

# ── Chart: model vs expected per category ────────────────────────────────────
st.subheader("📊 Average Score: Model vs Expected")
labels = [f[0] for f in SCORE_FIELDS]
model_avgs    = [filtered[f[1]].mean() for f in SCORE_FIELDS]
expected_avgs = [filtered[f[2]].mean() for f in SCORE_FIELDS]

fig = go.Figure([
    go.Bar(name="Model",    x=labels, y=model_avgs,    marker_color="#1f77b4"),
    go.Bar(name="Expected", x=labels, y=expected_avgs, marker_color="#ff7f0e"),
])
fig.update_layout(barmode="group", height=350, margin=dict(t=20, b=20))
st.plotly_chart(fig, use_container_width=True)

st.divider()

# ── Per-record table ─────────────────────────────────────────────────────────
st.subheader("📋 Records")

header = st.columns([2.5, 1, 1, 1, 1, 1, 1, 1, 1])
for col, label in zip(header, ["Prompt", "Content", "Structure", "Linguistic", "Form", "Grammar", "Vocab", "Spelling", "Details"]):
    col.markdown(f"**{label}**")
st.divider()

for idx, row in filtered.iterrows():
    cols = st.columns([2.5, 1, 1, 1, 1, 1, 1, 1, 1])
    cols[0].write(row["prompt"])

    for i, (_, model_key, exp_key, _) in enumerate(SCORE_FIELDS):
        m, e = row[model_key], row[exp_key]
        color = "#2ca02c" if m == e else ("#d62728" if m < e else "#ff7f0e")
        cols[i + 1].markdown(
            f"<span style='color:{color};font-weight:bold'>{m}</span> / <span style='color:gray'>{e}</span>",
            unsafe_allow_html=True
        )

    if cols[8].button("🔍", key=f"detail_{idx}"):
        st.session_state[f"show_{idx}"] = not st.session_state.get(f"show_{idx}", False)

    if st.session_state.get(f"show_{idx}", False):
        doc = get_collection().find_one({"_id": ObjectId(row["id"])})
        if doc:
            ee   = doc.get("scoring_response", {}).get("services", {}).get("essay_evaluation", {})
            t1, t2, t3, t4 = st.tabs(["📝 Essay", "💬 Feedback", "🗒️ Remark", "📄 Raw JSON"])

            with t1:
                st.markdown("**Prompt**")
                st.info(doc.get("essay_prompt", ""))
                st.markdown("**Essay Text**")
                st.text_area("", doc.get("essay_text", ""), height=200, key=f"essay_{idx}")

            with t2:
                for label, key in [("Content", "content_feedback"), ("Structure", "structure_feedback"), ("Linguistic", "linguistic_feedback")]:
                    fb = ee.get(key, "")
                    if fb:
                        st.markdown(f"**{label}**")
                        st.info(fb)

            with t3:
                st.write(doc.get("remark", "") or "_(no remark)_")

            with t4:
                doc["_id"] = str(doc["_id"])
                st.json(doc)

    st.divider()

if st.sidebar.button("🔄 Refresh"):
    st.cache_data.clear()
    st.rerun()
