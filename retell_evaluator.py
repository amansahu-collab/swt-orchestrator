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
</style>
""", unsafe_allow_html=True)

API_BASE = "https://la-model-proofreading-staging.languageacademy.com.au"
TRANSCRIBE_API = "http://whisper-model-2057542621.ap-southeast-2.elb.amazonaws.com/api/v1/transcribe"
TRANSCRIBE_TOKEN = "GtJvj921H861LS0EOvzyGp7fk"
MONGO_URI = "mongodb+srv://amansahu_db_user:12121212qwqw@cluster0.4hzwf6o.mongodb.net/"
MONGO_DB = "remark"
MONGO_COLLECTION = "retell"


@st.cache_resource
def get_mongo_collection():
    """Return the MongoDB collection used to store retell reports.

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

    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=10000)
    return client[MONGO_DB][MONGO_COLLECTION]


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
if 'last_retell_result' not in st.session_state:
    st.session_state.last_retell_result = None
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
                st.metric("Score", f"{item['score']}/6")
                st.caption(f"Key Points: {item['total_points']}")
    else:
        st.info("No evaluations yet")

    if st.button("Clear History", use_container_width=True):
        st.session_state.retell_history = []
        st.rerun()

st.markdown('<h1 class="main-header">🎓 Retell Lecture Evaluator</h1>', unsafe_allow_html=True)
st.markdown("Evaluate student's ability to retell lecture content by analyzing key point coverage")

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

_, col_btn, _ = st.columns([1, 1, 1])
with col_btn:
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
                    timeout=60  ,
                    verify=False
                )

                if response.status_code == 200:
                    result = response.json()
                    final_result = result.get('final_result', {})
                    agent1 = result.get('agent_1_key_point_extractor', {}).get('output', {})
                    agent2 = result.get('agent_2_coverage_evaluator', {}).get('output', {})

                    total_key_points = final_result.get('total_key_points', 0)
                    overall_relevancy_percentage = final_result.get('overall_relevancy_percentage', 0)
                    content_score = final_result.get('content_score', 0)
                    content_score_90 = final_result.get('content_score_90', 0)
                    key_point_results = final_result.get('key_point_results', [])
                    feedback_text = result.get('feedback', {}).get('feedback', '')
                    agent3 = result.get('agent_3_feedback_generator', {}).get('output', {})

                    st.session_state.retell_history.append({
                        'timestamp': datetime.now().strftime("%H:%M:%S"),
                        'score': content_score,
                        'total_points': total_key_points
                    })

                    # Persist the latest result so the report form survives reruns
                    st.session_state.last_retell_result = result
                    st.session_state.last_content_score_90 = content_score_90

                    st.success("✅ Retell evaluation completed successfully!")
                    st.divider()

                    col_score1, col_score2 = st.columns([3, 2])
                    with col_score1:
                        fig = go.Figure(go.Indicator(
                            mode="gauge+number+delta",
                            value=content_score_90,
                            domain={'x': [0, 1], 'y': [0, 1]},
                            title={'text': "Content Score (out of 90)", 'font': {'size': 24}},
                            gauge={
                                'axis': {'range': [0, 90], 'tickwidth': 1},
                                'bar': {'color': "#667eea"},
                                'steps': [
                                    {'range': [0, 30], 'color': "#fee"},
                                    {'range': [30, 60], 'color': "#ffe"},
                                    {'range': [60, 90], 'color': "#efe"}
                                ],
                                'threshold': {'line': {'color': "red", 'width': 4}, 'thickness': 0.75, 'value': 60}
                            }
                        ))
                        fig.update_layout(height=250, margin=dict(l=20, r=20, t=50, b=20))
                        st.plotly_chart(fig, use_container_width=True)

                    with col_score2:
                        st.metric("Content Score", f"{content_score}/6")
                        st.metric("Content Score (90)", f"{content_score_90}/90")
                        st.metric("Total Key Points", total_key_points)
                        st.metric("Overall Relevancy", f"{overall_relevancy_percentage}%")
                        if content_score >= 5:
                            st.success("🎉 Excellent Coverage")
                        elif content_score >= 3:
                            st.warning("⚠️ Good Coverage")
                        else:
                            st.error("❌ Needs Improvement")

                    if feedback_text:
                        st.subheader("💬 Feedback")
                        st.info(feedback_text)

                    st.divider()
                    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 Individual Coverage", "📊 Overall Analysis", "📚 Extracted Key Points", "🤖 Agent Details", "📄 Raw Data"])

                    with tab1:
                        st.subheader("Individual Key Point Coverage")
                        if key_point_results:
                            for idx, kp in enumerate(key_point_results, 1):
                                coverage = kp.get('coverage_percentage', 0)
                                if coverage >= 80:
                                    color, status = "#28a745", "Excellent"
                                elif coverage >= 60:
                                    color, status = "#17a2b8", "Good"
                                elif coverage >= 40:
                                    color, status = "#ffc107", "Fair"
                                elif coverage >= 20:
                                    color, status = "#fd7e14", "Poor"
                                else:
                                    color, status = "#dc3545", "Not Covered"
                                st.markdown(f"**Key Point {idx}:** {kp.get('key_point', '')}")
                                c1, c2 = st.columns([3, 1])
                                with c1:
                                    st.progress(coverage / 100)
                                with c2:
                                    st.markdown(f"<span style='color: {color}; font-weight: bold;'>{coverage}% - {status}</span>", unsafe_allow_html=True)
                                st.markdown("---")
                        else:
                            st.info("No individual coverage data available")

                    with tab2:
                        st.subheader("Overall Relevancy Assessment")
                        st.progress(overall_relevancy_percentage / 100)
                        st.write(f"**Overall Relevancy Score: {overall_relevancy_percentage}%**")
                        if overall_relevancy_percentage >= 80:
                            st.success("🎉 Excellent relevancy!")
                        elif overall_relevancy_percentage >= 60:
                            st.success("👍 Good relevancy!")
                        elif overall_relevancy_percentage >= 40:
                            st.warning("⚠️ Fair relevancy.")
                        elif overall_relevancy_percentage >= 20:
                            st.warning("⚠️ Below average.")
                        else:
                            st.error("❌ Poor relevancy.")
                        st.markdown("---")
                        col_c1, col_c2 = st.columns(2)
                        with col_c1:
                            st.markdown("**Score Calculation:**")
                            st.write(f"• Total Key Points: {total_key_points}")
                            st.write(f"• Overall Relevancy: {overall_relevancy_percentage}%")
                            st.write(f"• Final Score: {content_score}/6")
                        with col_c2:
                            st.markdown("**Score Mapping:**")
                            for line in ["≥65% → 6", "50-64% → 5", "35-49% → 4", "25-34% → 3", "15-24% → 2", "5-14% → 1", "<5% → 0"]:
                                st.write(f"• {line}")
                        st.markdown(f"**{overall_relevancy_percentage}% falls in range → Score {content_score}**")

                    with tab3:
                        st.subheader("Extracted Key Points from Lecture")
                        for idx, point in enumerate(agent1.get('key_points', []), 1):
                            st.write(f"{idx}. {point}")

                    with tab4:
                        c1, c2, c3 = st.columns(3)
                        with c1:
                            st.subheader("Agent 1: Key Point Extractor")
                            st.json(agent1)
                        with c2:
                            st.subheader("Agent 2: Coverage Evaluator")
                            st.json(agent2)
                        with c3:
                            st.subheader("Agent 3: Feedback Generator")
                            st.json(agent3)

                    with tab5:
                        st.subheader("Complete API Response")
                        st.json(result)

                elif response.status_code == 401:
                    st.error("🔒 Authentication failed. Please check your API token.")
                elif response.status_code == 404:
                    st.error("🔍 API endpoint not found.")
                else:
                    st.error(f"❌ Error {response.status_code}: {response.text}")

        except requests.exceptions.Timeout:
            st.error("⏱️ Request timed out. Please try again.")
        except requests.exceptions.ConnectionError:
            st.error("🔌 Connection failed.")
        except Exception as e:
            st.error(f"❌ Unexpected error: {str(e)}")

# --- Report an incorrect result ---
if st.session_state.last_retell_result is not None:
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
                            retell_response=st.session_state.last_retell_result,
                        )
                    st.success(f"✅ Report submitted successfully! Reference ID: {report_id}")
                except Exception as e:
                    st.error(f"❌ Failed to submit report: {str(e)}")

st.divider()
st.caption("💡 Tip: Use the sidebar to view your evaluation history and configure the API token")
