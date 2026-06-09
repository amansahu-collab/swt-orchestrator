import streamlit as st
import requests
from datetime import datetime
import plotly.graph_objects as go
import urllib3

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

if 'retell_history' not in st.session_state:
    st.session_state.retell_history = []

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
    student_input = st.text_area("", height=250, placeholder="Enter what the student said when retelling the lecture...", key="student")

_, col_btn, _ = st.columns([1, 1, 1])
with col_btn:
    evaluate_btn = st.button("🚀 Evaluate Retell", use_container_width=True, type="primary")

if evaluate_btn:
    if not lecture_input or not student_input:
        st.error("⚠️ Please provide both lecture transcript and student response.")
    else:
        with st.spinner("🔄 Analyzing retell performance..."):
            try:
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

                    st.success("✅ Retell evaluation completed successfully!")
                    st.divider()

                    col_score1, col_score2 = st.columns([3, 2])
                    with col_score1:
                        fig = go.Figure(go.Indicator(
                            mode="gauge+number+delta",
                            value=content_score,
                            domain={'x': [0, 1], 'y': [0, 1]},
                            title={'text': "Content Score", 'font': {'size': 24}},
                            gauge={
                                'axis': {'range': [0, 6], 'tickwidth': 1},
                                'bar': {'color': "#667eea"},
                                'steps': [
                                    {'range': [0, 2], 'color': "#fee"},
                                    {'range': [2, 4], 'color': "#ffe"},
                                    {'range': [4, 6], 'color': "#efe"}
                                ],
                                'threshold': {'line': {'color': "red", 'width': 4}, 'thickness': 0.75, 'value': 4}
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

st.divider()
st.caption("💡 Tip: Use the sidebar to view your evaluation history and configure the API token")
