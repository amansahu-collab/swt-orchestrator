import streamlit as st
import requests
from datetime import datetime, timezone
import plotly.graph_objects as go
import urllib3
from pymongo import MongoClient

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(page_title="Retell Lecture Evaluator", page_icon="🎓", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
    }
    .key-point {
        padding: 8px 12px;
        margin: 4px 0;
        border-radius: 6px;
        border-left: 4px solid;
    }
    .covered {
        background-color: #d4edda;
        border-left-color: #28a745;
    }
    .partial {
        background-color: #fff3cd;
        border-left-color: #ffc107;
    }
    .not-covered {
        background-color: #f8d7da;
        border-left-color: #dc3545;
    }
    .incorrect {
        background-color: #f5c6cb;
        border-left-color: #721c24;
    }
    .feedback-box {
        background-color: #00000;
        border-left: 5px solid #667eea;
        padding: 16px 20px;
        border-radius: 8px;
        font-size: 1.05rem;
        line-height: 1.6;
    }
    .version-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 6px;
        font-weight: 700;
        font-size: 0.9rem;
        color: #fff;
    }
    .v2-badge { background-color: #667eea; }
</style>
""", unsafe_allow_html=True)

API_BASE = "https://la-model-proofreading-staging.languageacademy.com.au"
TRANSCRIBE_API = "http://whisper-model-2057542621.ap-southeast-2.elb.amazonaws.com/api/v1/transcribe"
TRANSCRIBE_TOKEN = "GtJvj921H861LS0EOvzyGp7fk"
MONGO_URI = "mongodb+srv://amansahu_db_user:12121212qwqw@cluster0.4hzwf6o.mongodb.net/"
MONGO_DB = "remark"
MONGO_COLLECTION = "retell"
# Separate collection that logs every evaluation call (input + output)
MONGO_CALLS_COLLECTION = "retell_calls"


@st.cache_resource
def _get_mongo_client():
    """Return a shared MongoClient.

    The mongodb+srv URI needs a DNS SRV lookup. Some machines' default DNS
    resolvers can't answer SRV queries, so we fall back to public DNS servers.
    """
    try:
        import dns.resolver
        dns.resolver.default_resolver = dns.resolver.Resolver(configure=True)
        # Add public DNS servers as fallbacks for SRV/TXT resolution
        existing = list(dns.resolver.default_resolver.nameservers)
        for ns in ("8.8.8.8", "1.1.1.1"):
            if ns not in existing:
                existing.append(ns)
        dns.resolver.default_resolver.nameservers = existing
    except Exception:
        pass

    return MongoClient(MONGO_URI, serverSelectionTimeoutMS=10000)


def get_mongo_collection():
    """Return the MongoDB collection used to store retell reports."""
    return _get_mongo_client()[MONGO_DB][MONGO_COLLECTION]


def get_calls_collection():
    """Return the MongoDB collection used to log every evaluation call."""
    return _get_mongo_client()[MONGO_DB][MONGO_CALLS_COLLECTION]


def save_call(lecture_transcript, student_transcript, student_audio_url, api_response_v2):
    """Persist every evaluation call (input + output) into MongoDB.

    Failures here should never break the UI, so errors are swallowed and
    surfaced only as a return value.
    """
    try:
        collection = get_calls_collection()
        document = {
            "input": {
                "lecture_transcript": lecture_transcript,
                "student_transcript": student_transcript,
                "student_audio_url": student_audio_url,
            },
            "output_v2": api_response_v2,
            "created_at": datetime.now(timezone.utc),
        }
        return collection.insert_one(document).inserted_id
    except Exception as e:
        return f"ERROR: {e}"


def save_report(expected_marks, remark, retell_response):
    """Persist a user-submitted report into MongoDB. Returns the inserted id."""
    collection = get_mongo_collection()
    document = {
        "expected_marks": expected_marks,
        "remark": remark,
        "retell_response": retell_response,
        "created_at": datetime.now(timezone.utc),
    }
    return collection.insert_one(document).inserted_id


def transcribe_audio(audio_url, reference_text=""):
    """Call the Whisper transcribe API and return the transcript text."""
    response = requests.post(
        TRANSCRIBE_API,
        headers={
            "accept": "application/json",
            "x-token": TRANSCRIBE_TOKEN,
            "Content-Type": "application/json",
        },
        json={"audio_url": audio_url, "reference_text": reference_text or "string"},
        timeout=120,
        verify=False,
    )
    response.raise_for_status()
    result = response.json()
    # API returns {"status": "success", "data": {"transcript": "...", ...}}
    data = result.get("data", result) if isinstance(result, dict) else result
    if isinstance(data, dict):
        for key in ("transcript", "text", "transcription", "result"):
            value = data.get(key)
            if value:
                return value if isinstance(value, str) else str(value)
    return ""


def call_retell(endpoint, lecture_transcript, student_transcript, token):
    """Call the retell endpoint (v2 = /retell-v2).

    Returns (status_code, json_or_text). On non-200 the second element is the
    raw text so the caller can surface an error message.
    """
    response = requests.post(
        f"{API_BASE}/{endpoint}",
        headers={"accept": "application/json", "Content-Type": "application/json"},
        json={
            "lecture_transcript": lecture_transcript,
            "student_transcript": student_transcript,
            "token": token,
        },
        timeout=60,
        verify=False,
    )
    if response.status_code == 200:
        return response.status_code, response.json()
    return response.status_code, response.text


def parse_retell_result(result, lecture_transcript, student_transcript):
    """Normalise a raw retell API response into the fields the UI needs."""
    final_result = result.get('final_result', {})
    agent1 = result.get('agent_1_key_point_extractor', {})
    lecture_kp_output = agent1.get('lecture_output', {})
    student_kp_output = agent1.get('student_output', {})
    agent2 = result.get('agent_2_coverage_evaluator', {}).get('output', {})
    feedback_obj = result.get('feedback', {}) or result.get('agent_3_feedback_generator', {}).get('output', {})
    feedback_text = feedback_obj.get('feedback', '')

    student_key_point_matches = (
        final_result.get('student_key_point_matches')
        or agent2.get('student_key_point_matches', [])
    )

    complete_result = {
        "lecture_transcript": lecture_transcript,
        "student_transcript": student_transcript,
        "final_result": final_result,
        "feedback": result.get('feedback', {}),
        "agent_1_key_point_extractor": result.get('agent_1_key_point_extractor', {}),
        "agent_2_coverage_evaluator": result.get('agent_2_coverage_evaluator', {}),
        "agent_3_feedback_generator": result.get('agent_3_feedback_generator', {}),
    }

    return {
        "complete_result": complete_result,
        "final_result": final_result,
        "lecture_kp_output": lecture_kp_output,
        "student_kp_output": student_kp_output,
        "agent2": agent2,
        "feedback_obj": feedback_obj,
        "feedback_text": feedback_text,
        "total_key_points": final_result.get('total_key_points', 0),
        "overall_relevancy_percentage": final_result.get('overall_relevancy_percentage', 0),
        "content_score": final_result.get('content_score', 0),
        "content_score_90": final_result.get('content_score_90', 0),
        "key_point_results": final_result.get('key_point_results', []),
        "student_key_point_matches": student_key_point_matches,
    }


def _coverage_color(coverage):
    if coverage >= 80:
        return "#28a745", "Excellent"
    elif coverage >= 60:
        return "#17a2b8", "Good"
    elif coverage >= 40:
        return "#ffc107", "Fair"
    elif coverage >= 20:
        return "#fd7e14", "Poor"
    return "#dc3545", "Not Covered"


def render_score_summary(data, key_prefix):
    """Render the gauge + metrics + feedback."""
    content_score_90 = data['content_score_90']
    final_result = data['final_result']

    # --- Response quality checks (shown up front) ---
    word_count = final_result.get('word_count')
    conclusion_marker_found = final_result.get('conclusion_marker_found')
    short_response_penalty_applied = final_result.get('short_response_penalty_applied')

    if word_count is not None or conclusion_marker_found is not None or short_response_penalty_applied is not None:
        q1, q2, q3 = st.columns(3)
        with q1:
            wc_display = word_count if word_count is not None else "—"
            st.metric("Word Count", wc_display)
            if word_count is not None and word_count < 50:
                st.caption("⚠️ Under 50 words — penalty applies")
        with q2:
            if conclusion_marker_found is True:
                st.success("✅ Conclusion marker found")
            elif conclusion_marker_found is False:
                st.error("❌ No conclusion marker")
            else:
                st.info("Conclusion marker: —")
        with q3:
            if short_response_penalty_applied is True:
                st.error("⚠️ Short-response penalty applied")
            elif short_response_penalty_applied is False:
                st.success("✅ No short-response penalty")
            else:
                st.info("Short-response penalty: —")
        st.caption("ℹ️ Responses under 50 words are penalised.")
        st.write("")

    col_score1, col_score2 = st.columns([3, 2])

    with col_score1:
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=content_score_90,
            domain={'x': [0, 1], 'y': [0, 1]},
            title={'text': "Content Score (/90)", 'font': {'size': 20}},
            gauge={
                'axis': {'range': [0, 90], 'tickwidth': 1},
                'bar': {'color': "#667eea"},
                'steps': [
                    {'range': [0, 30], 'color': "#fee"},
                    {'range': [30, 60], 'color': "#ffe"},
                    {'range': [60, 90], 'color': "#efe"}
                ],
                'threshold': {'line': {'color': "red", 'width': 4}, 'thickness': 0.75, 'value': 80}
            }
        ))
        fig.update_layout(height=230, margin=dict(l=20, r=20, t=50, b=20))
        st.plotly_chart(fig, use_container_width=True, key=f"gauge_{key_prefix}")

    with col_score2:
        st.metric("Content Score", f"{content_score_90}/90")
        st.metric("Lecture Key Points", data['total_key_points'])
        st.metric("Overall Relevancy", f"{data['overall_relevancy_percentage']}%")

        if content_score_90 >= 80:
            st.success("🎉 Excellent Coverage")
        elif content_score_90 >= 50:
            st.warning("⚠️ Good Coverage")
        else:
            st.error("❌ Needs Improvement")

    if data['feedback_text']:
        st.markdown("**📝 Feedback**")
        st.markdown(f'<div class="feedback-box">{data["feedback_text"]}</div>', unsafe_allow_html=True)


def render_key_point_matches(data):
    """Render the Key Point Matches table."""
    student_key_point_matches = data['student_key_point_matches']
    if not student_key_point_matches:
        st.info("No key point match data available")
        return

    match_table_rows = []
    for idx, item in enumerate(student_key_point_matches, 1):
        skp = item.get('student_key_point', '')
        matches = item.get('matches', [])
        match_count = len(matches)
        if matches:
            for m_idx, m in enumerate(matches):
                match_table_rows.append({
                    "Student Key Point": f"S{idx}. {skp}" if m_idx == 0 else "",
                    "Matches": f"{match_count} lecture point(s)" if m_idx == 0 else "",
                    "Matched Lecture Key Point": m.get('lecture_key_point', ''),
                    "Coverage": f"{m.get('coverage_percentage', 0)}%",
                })
        else:
            match_table_rows.append({
                "Student Key Point": f"S{idx}. {skp}",
                "Matches": "0 (not matched)",
                "Matched Lecture Key Point": "No lecture key point matched",
                "Coverage": "0%",
            })
    st.table(match_table_rows)


def render_key_points(data):
    """Render extracted lecture + student key points."""
    col_kp1, col_kp2 = st.columns(2)
    with col_kp1:
        st.markdown("**📚 Lecture Key Points**")
        lecture_key_points = data['lecture_kp_output'].get('key_points', [])
        if lecture_key_points:
            for idx, point in enumerate(lecture_key_points, 1):
                st.write(f"{idx}. {point}")
        else:
            st.info("No lecture key points extracted")
    with col_kp2:
        st.markdown("**🎤 Student Key Points**")
        student_key_points = data['student_kp_output'].get('key_points', [])
        if student_key_points:
            for idx, point in enumerate(student_key_points, 1):
                st.write(f"{idx}. {point}")
        else:
            st.info("No student key points extracted")


def render_coverage(data):
    """Render coverage per lecture key point."""
    key_point_results = data['key_point_results']
    if not key_point_results:
        st.info("No lecture key point coverage data available")
        return
    for idx, kp_result in enumerate(key_point_results, 1):
        coverage = kp_result.get('coverage_percentage', 0)
        key_point = kp_result.get('key_point', '')
        color, status = _coverage_color(coverage)
        st.markdown(f"**Key Point {idx}:** {key_point}")
        c1, c2 = st.columns([3, 1])
        with c1:
            st.progress(min(coverage, 100) / 100)
        with c2:
            st.markdown(f"<span style='color: {color}; font-weight: bold;'>{coverage}% - {status}</span>", unsafe_allow_html=True)
        st.markdown("---")


if 'retell_history' not in st.session_state:
    st.session_state.retell_history = []
if 'last_retell_response' not in st.session_state:
    st.session_state.last_retell_response = None
if 'last_content_score_90' not in st.session_state:
    st.session_state.last_content_score_90 = 0

with st.sidebar:
    st.header("⚙️ Configuration")
    api_token = st.text_input("API Token", value="pte_lsahdpasdhfasdhfasuaosiudfg", type="password")

    st.divider()
    st.header("📊 Evaluation History")
    if st.session_state.retell_history:
        for idx, item in enumerate(reversed(st.session_state.retell_history[-5:])):
            with st.expander(f"#{len(st.session_state.retell_history) - idx} - {item['timestamp']}"):
                st.metric("Score", f"{item.get('score', 0)}/90")
                st.caption(f"Key Points: {item.get('total_points', 0)}")
    else:
        st.info("No evaluations yet")

    if st.button("Clear History", use_container_width=True):
        st.session_state.retell_history = []
        st.rerun()

st.markdown('<h1 class="main-header">🎓 Retell Lecture Evaluator</h1>', unsafe_allow_html=True)
st.markdown("Evaluate a student's retell against the API to review key points and key point matches.")

col1, col2 = st.columns(2)

with col1:
    st.subheader("📚 Lecture Transcript")
    lecture_input = st.text_area("", height=250, placeholder="Paste the original lecture transcript here...", key="lecture")

with col2:
    st.subheader("🎤 Student Response")
    input_mode = st.radio(
        "Response input type",
        ["Text", "Audio URL"],
        horizontal=True,
        key="student_input_mode",
    )
    if input_mode == "Text":
        student_input = st.text_area("", height=210, placeholder="Enter what the student said when retelling the lecture...", key="student")
        student_audio_url = ""
    else:
        student_audio_url = st.text_input(
            "Audio URL",
            placeholder="https://.../answer.wav",
            key="student_audio_url",
        )
        st.caption("The audio will be transcribed automatically and used as the student response.")
        student_input = ""

col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 1])
with col_btn2:
    evaluate_btn = st.button("🚀 Evaluate Retell", use_container_width=True, type="primary")

if evaluate_btn:
    missing = not lecture_input or (input_mode == "Text" and not student_input) or (input_mode == "Audio URL" and not student_audio_url)
    if missing:
        st.error("⚠️ Please provide the lecture transcript and the student response (text or audio URL).")
    else:
        try:
            if input_mode == "Audio URL":
                with st.spinner("🎧 Transcribing student audio..."):
                    student_input = transcribe_audio(student_audio_url, reference_text=lecture_input)
                if not student_input or not student_input.strip():
                    st.error("❌ Transcription returned no text. Please check the audio URL and try again.")
                    st.stop()
                st.success("✅ Audio transcribed successfully!")
                with st.expander("📝 Transcribed Student Response", expanded=True):
                    st.write(student_input)

            with st.spinner("🔄 Analyzing retell performance..."):
                status_v2, result_v2 = call_retell("retell-v2", lecture_input, student_input, api_token)

            # Handle failure
            if status_v2 != 200:
                if status_v2 == 401:
                    st.error("🔒 Authentication failed. Please check your API token.")
                elif status_v2 == 404:
                    st.error("🔍 API endpoint not found.")
                else:
                    st.error(f"❌ Error {status_v2}: {result_v2}")
            else:
                data_v2 = parse_retell_result(result_v2, lecture_input, student_input)

                # Log the call to MongoDB
                call_id = save_call(
                    lecture_transcript=lecture_input,
                    student_transcript=student_input,
                    student_audio_url=student_audio_url,
                    api_response_v2=result_v2,
                )

                st.session_state.retell_history.append({
                    'timestamp': datetime.now().strftime("%H:%M:%S"),
                    'score': data_v2['content_score_90'],
                    'total_points': data_v2['total_key_points'],
                })

                st.session_state.last_retell_response = {
                    "v2": data_v2['complete_result'],
                }
                st.session_state.last_content_score_90 = data_v2['content_score_90']

                st.success("✅ Retell evaluation completed!")
                if isinstance(call_id, str) and call_id.startswith("ERROR:"):
                    st.warning(f"⚠️ Could not log this call to MongoDB: {call_id[7:].strip()}")
                else:
                    st.caption(f"🗄️ Call logged to MongoDB (`{MONGO_DB}.{MONGO_CALLS_COLLECTION}`) — id: {call_id}")

                st.divider()

                # Full result panel
                render_score_summary(data_v2, key_prefix="v2")
                st.markdown("##### 🔗 Key Point Matches")
                render_key_point_matches(data_v2)
                st.markdown("##### 📚 Extracted Key Points")
                render_key_points(data_v2)

                st.divider()

                # Detailed tabs
                tab_cov, tab_agent, tab_raw = st.tabs([
                    "📊 Coverage",
                    "🤖 Agent Details",
                    "📄 Raw Data",
                ])

                with tab_cov:
                    render_coverage(data_v2)

                with tab_agent:
                    st.markdown("**Agent 1 — Lecture Output**")
                    st.json(data_v2['lecture_kp_output'])
                    st.markdown("**Agent 1 — Student Output**")
                    st.json(data_v2['student_kp_output'])
                    st.markdown("**Agent 2 — Coverage Evaluator**")
                    st.json(data_v2['agent2'])
                    st.markdown("**Agent 3 — Feedback**")
                    st.json(data_v2['feedback_obj'])

                with tab_raw:
                    st.json(data_v2['complete_result'])

        except requests.exceptions.Timeout:
            st.error("⏱️ Request timed out. Please try again.")
        except requests.exceptions.ConnectionError:
            st.error("🔌 Connection failed. Please check if the API server is running.")
        except Exception as e:
            st.error(f"❌ Unexpected error: {str(e)}")

# --- Report an incorrect result ---
if st.session_state.last_retell_response is not None:
    st.divider()
    with st.expander("🚩 Report this result", expanded=False):
        st.caption(
            "If the score or feedback looks wrong, submit the marks you expected along with a remark. "
            "This is stored for review together with the full evaluation response."
        )
        with st.form("report_form", clear_on_submit=True):
            expected_marks = st.number_input(
                "Expected marks (out of 90)",
                min_value=0,
                max_value=90,
                value=int(st.session_state.last_content_score_90 or 0),
                step=1,
            )
            remark = st.text_area(
                "Remark",
                placeholder="Explain what you think is incorrect about the score or feedback...",
                height=120,
            )
            submit_report = st.form_submit_button("📤 Submit Report", type="primary", use_container_width=True)

        if submit_report:
            if not remark or not remark.strip():
                st.warning("⚠️ Please add a remark describing the issue before submitting.")
            else:
                try:
                    with st.spinner("💾 Submitting report..."):
                        report_id = save_report(
                            expected_marks=int(expected_marks),
                            remark=remark.strip(),
                            retell_response=st.session_state.last_retell_response,
                        )
                    st.success(f"✅ Report submitted successfully! Reference ID: {report_id}")
                except Exception as e:
                    st.error(f"❌ Failed to submit report: {str(e)}")

st.divider()
st.caption("💡 Tip: Each evaluation calls /retell-v2 to review key points and key point matches.")
