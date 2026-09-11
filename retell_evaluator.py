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
        background-color: #eef2ff;
        border-left: 5px solid #667eea;
        padding: 16px 20px;
        border-radius: 8px;
        font-size: 1.05rem;
        line-height: 1.6;
    }
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


def save_call(lecture_transcript, student_transcript, student_audio_url, api_response):
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
            "output": api_response,
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
                st.metric("Score", f"{item['score']}/90")
                st.caption(f"Lecture Key Points: {item['total_points']}")
    else:
        st.info("No evaluations yet")

    if st.button("Clear History", use_container_width=True):
        st.session_state.retell_history = []
        st.rerun()

st.markdown('<h1 class="main-header">🎓 Retell Lecture Evaluator</h1>', unsafe_allow_html=True)
st.markdown("Evaluate a student's ability to retell lecture content by matching student key points to lecture key points")

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
                response = requests.post(
                    f"{API_BASE}/retell",
                    headers={"accept": "application/json", "Content-Type": "application/json"},
                    json={"lecture_transcript": lecture_input, "student_transcript": student_input, "token": api_token},
                    timeout=60,
                    verify=False
                )

                if response.status_code == 200:
                    result = response.json()

                    # Log every call (input + output) to a separate MongoDB collection
                    call_id = save_call(
                        lecture_transcript=lecture_input,
                        student_transcript=student_input,
                        student_audio_url=student_audio_url,
                        api_response=result,
                    )

                    # Create complete response object with inputs (like other UIs)
                    complete_result = {
                        "lecture_transcript": lecture_input,
                        "student_transcript": student_input,
                        "final_result": result.get('final_result', {}),
                        "feedback": result.get('feedback', {}),
                        "agent_1_key_point_extractor": result.get('agent_1_key_point_extractor', {}),
                        "agent_2_coverage_evaluator": result.get('agent_2_coverage_evaluator', {}),
                        "agent_3_feedback_generator": result.get('agent_3_feedback_generator', {})
                    }

                    final_result = result.get('final_result', {})
                    agent1 = result.get('agent_1_key_point_extractor', {})
                    lecture_kp_output = agent1.get('lecture_output', {})
                    student_kp_output = agent1.get('student_output', {})
                    agent2 = result.get('agent_2_coverage_evaluator', {}).get('output', {})
                    feedback_obj = result.get('feedback', {}) or result.get('agent_3_feedback_generator', {}).get('output', {})
                    feedback_text = feedback_obj.get('feedback', '')

                    total_key_points = final_result.get('total_key_points', 0)
                    overall_relevancy_percentage = final_result.get('overall_relevancy_percentage', 0)
                    content_score = final_result.get('content_score', 0)
                    content_score_90 = final_result.get('content_score_90', 0)
                    key_point_results = final_result.get('key_point_results', [])
                    student_key_point_matches = (
                        final_result.get('student_key_point_matches')
                        or agent2.get('student_key_point_matches', [])
                    )

                    st.session_state.retell_history.append({
                        'timestamp': datetime.now().strftime("%H:%M:%S"),
                        'score': content_score_90,
                        'total_points': total_key_points
                    })

                    st.session_state.last_retell_response = complete_result
                    st.session_state.last_content_score_90 = content_score_90

                    st.success("✅ Retell evaluation completed successfully!")
                    if isinstance(call_id, str) and call_id.startswith("ERROR:"):
                        st.warning(f"⚠️ Could not log this call to MongoDB: {call_id[7:].strip()}")
                    else:
                        st.caption(f"🗄️ Call logged to MongoDB (`{MONGO_DB}.{MONGO_CALLS_COLLECTION}`) — id: {call_id}")

                    st.divider()
                    col_score1, col_score2 = st.columns([3, 2])

                    with col_score1:
                        # Content score gauge (10-90 scale)
                        fig = go.Figure(go.Indicator(
                            mode="gauge+number",
                            value=content_score_90,
                            domain={'x': [0, 1], 'y': [0, 1]},
                            title={'text': "Content Score (/90)", 'font': {'size': 24}},
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
                        fig.update_layout(height=250, margin=dict(l=20, r=20, t=50, b=20))
                        st.plotly_chart(fig, use_container_width=True)

                    with col_score2:
                        st.metric("Content Score", f"{content_score_90}/90")
                        st.metric("Lecture Key Points", total_key_points)
                        st.metric("Overall Relevancy", f"{overall_relevancy_percentage}%")

                        # Score interpretation (based on 10-90 scale)
                        if content_score_90 >= 80:
                            st.success("🎉 Excellent Coverage")
                        elif content_score_90 >= 50:
                            st.warning("⚠️ Good Coverage")
                        else:
                            st.error("❌ Needs Improvement")

                    # Feedback section
                    if feedback_text:
                        st.divider()
                        st.subheader("📝 Student Feedback")
                        st.markdown(f'<div class="feedback-box">{feedback_text}</div>', unsafe_allow_html=True)

                    # Score calculation breakdown
                    st.divider()
                    st.subheader("🧮 Score Calculation")

                    col_calc1, col_calc2 = st.columns(2)

                    with col_calc1:
                        st.markdown("**How the score is derived:**")
                        st.write(f"• Total Lecture Key Points: {total_key_points}")
                        st.write(f"• Best coverage taken per lecture key point")
                        st.write(f"• Top 50% best-covered key points averaged")
                        st.write(f"• Overall Relevancy: {overall_relevancy_percentage}%")
                        st.markdown(f"**Content Score: {content_score_90}/90**")

                    with col_calc2:
                        st.markdown("**Scale details:**")
                        st.write("• Content score is clamped to the 10-90 range")
                        st.write("• Uncovered/weaker half never penalizes")
                        st.write(f"• Legacy 6-point band: {content_score}/6")

                    # Key point match table (main screen, below score calculation)
                    st.divider()
                    st.subheader("🔗 Key Point Matches")
                    st.caption("Which student key point matched which lecture key point(s), with coverage %")

                    if student_key_point_matches:
                        match_table_rows = []
                        for idx, item in enumerate(student_key_point_matches, 1):
                            skp = item.get('student_key_point', '')
                            matches = item.get('matches', [])
                            match_count = len(matches)
                            if matches:
                                for m_idx, m in enumerate(matches):
                                    match_table_rows.append({
                                        "Student Key Point": f"S{idx}. {skp}",
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
                        st.caption(
                            "Each student key point (S1, S2, ...) is listed against the lecture key point(s) it matched. "
                            "A student key point can match more than one lecture key point; the 'Matches' column shows how many, "
                            "and 'Coverage' shows how much of each lecture point's meaning was expressed."
                        )
                    else:
                        st.info("No key point match data available")

                    st.divider()

                    # Detailed analysis tabs
                    tab1, tab2, tab3, tab4, tab5 = st.tabs([
                        "📊 Lecture Key Point Coverage",
                        "🔗 Student Matches",
                        "📚 Extracted Key Points",
                        "🤖 Agent Details",
                        "📄 Raw Data"
                    ])

                    with tab1:
                        st.subheader("Coverage per Lecture Key Point")

                        if key_point_results:
                            for idx, kp_result in enumerate(key_point_results, 1):
                                coverage = kp_result.get('coverage_percentage', 0)
                                key_point = kp_result.get('key_point', '')

                                # Color coding based on coverage
                                if coverage >= 80:
                                    color = "#28a745"  # Green
                                    status = "Excellent"
                                elif coverage >= 60:
                                    color = "#17a2b8"  # Blue
                                    status = "Good"
                                elif coverage >= 40:
                                    color = "#ffc107"  # Yellow
                                    status = "Fair"
                                elif coverage >= 20:
                                    color = "#fd7e14"  # Orange
                                    status = "Poor"
                                else:
                                    color = "#dc3545"  # Red
                                    status = "Not Covered"

                                st.markdown(f"**Key Point {idx}:** {key_point}")

                                c1, c2 = st.columns([3, 1])
                                with c1:
                                    st.progress(min(coverage, 100) / 100)
                                with c2:
                                    st.markdown(f"<span style='color: {color}; font-weight: bold;'>{coverage}% - {status}</span>", unsafe_allow_html=True)

                                st.markdown("---")
                        else:
                            st.info("No lecture key point coverage data available")

                    with tab2:
                        st.subheader("Student Key Point Matches")
                        st.caption("Each student key point, how many lecture key points it matched, and the coverage % for each match")

                        if student_key_point_matches:
                            # Summary table: one row per student key point
                            summary_rows = []
                            for idx, item in enumerate(student_key_point_matches, 1):
                                skp = item.get('student_key_point', '')
                                matches = item.get('matches', [])
                                match_count = len(matches)
                                best_cov = max((m.get('coverage_percentage', 0) for m in matches), default=0)
                                summary_rows.append({
                                    "#": idx,
                                    "Student Key Point": skp,
                                    "Lecture Points Matched": match_count,
                                    "Best Coverage": f"{best_cov}%" if matches else "—",
                                    "Status": "Matched" if matches else "No match",
                                })

                            st.markdown("**Summary**")
                            st.table(summary_rows)

                            # Detailed table: one row per (student key point -> lecture key point) pair
                            detail_rows = []
                            for idx, item in enumerate(student_key_point_matches, 1):
                                skp = item.get('student_key_point', '')
                                matches = item.get('matches', [])
                                if matches:
                                    for m in matches:
                                        detail_rows.append({
                                            "Student #": idx,
                                            "Student Key Point": skp,
                                            "Matched Lecture Key Point": m.get('lecture_key_point', ''),
                                            "Coverage": f"{m.get('coverage_percentage', 0)}%",
                                        })
                                else:
                                    detail_rows.append({
                                        "Student #": idx,
                                        "Student Key Point": skp,
                                        "Matched Lecture Key Point": "— (no lecture key point matched)",
                                        "Coverage": "0%",
                                    })

                            st.markdown("**Detailed Matches**")
                            st.table(detail_rows)
                        else:
                            st.info("No student match data available")

                    with tab3:
                        col_kp1, col_kp2 = st.columns(2)

                        with col_kp1:
                            st.subheader("📚 Lecture Key Points")
                            lecture_key_points = lecture_kp_output.get('key_points', [])
                            if lecture_key_points:
                                for idx, point in enumerate(lecture_key_points, 1):
                                    st.write(f"{idx}. {point}")
                            else:
                                st.info("No lecture key points extracted")

                        with col_kp2:
                            st.subheader("🎤 Student Key Points")
                            student_key_points = student_kp_output.get('key_points', [])
                            if student_key_points:
                                for idx, point in enumerate(student_key_points, 1):
                                    st.write(f"{idx}. {point}")
                            else:
                                st.info("No student key points extracted")

                    with tab4:
                        st.subheader("Agent 1: Key Point Extractor")
                        col_agent1a, col_agent1b = st.columns(2)
                        with col_agent1a:
                            st.markdown("**Lecture Output**")
                            st.json(lecture_kp_output)
                        with col_agent1b:
                            st.markdown("**Student Output**")
                            st.json(student_kp_output)

                        st.divider()
                        st.subheader("Agent 2: Key Point Matcher")
                        st.json(agent2)

                        st.divider()
                        st.subheader("Agent 3: Feedback Generator")
                        st.json(feedback_obj)

                    with tab5:
                        st.subheader("Complete API Response")
                        st.json(complete_result)

                elif response.status_code == 401:
                    st.error("🔒 Authentication failed. Please check your API token.")
                elif response.status_code == 404:
                    st.error("🔍 API endpoint not found. Please verify the API URL.")
                else:
                    st.error(f"❌ Error {response.status_code}: {response.text}")

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
st.caption("💡 Tip: Use the sidebar to view your evaluation history and configure the API token")
