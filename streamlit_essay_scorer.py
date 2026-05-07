import streamlit as st
import requests
import json
from typing import Dict, Any

# Page config
st.set_page_config(
    page_title="Essay Scorer Pro",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS for dynamic, engaging styling
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

/* ---------- GLOBAL ---------- */

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

.stApp {
    background: #f4f7fb;
    color: #1e293b;
}

.block-container {
    max-width: 1450px;
    padding-top: 1rem !important;
    padding-bottom: 1rem !important;
    padding-left: 1.8rem !important;
    padding-right: 1.8rem !important;
}

/* ---------- MAIN CONTAINER ---------- */

.main-container {
    background: white;
    border-radius: 24px;
    padding: 1.8rem;
    border: 1px solid #e2e8f0;
    box-shadow: 0 8px 40px rgba(15, 23, 42, 0.06);
}

/* ---------- HEADER ---------- */

.header-section {
    text-align: center;
    margin-bottom: 1.5rem;
    margin-top: -0.4rem;
}

.main-title {
    font-size: 3rem;
    font-weight: 700;
    line-height: 1.1;
    margin-bottom: 0.5rem;

    background: linear-gradient(135deg, #6366f1, #8b5cf6);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}

.subtitle {
    color: #64748b;
    font-size: 1rem;
    margin-bottom: 0;
}

/* ---------- CONFIG ---------- */

.stExpander {
    border-radius: 16px !important;
    border: 1px solid #e2e8f0 !important;
    overflow: hidden;
    background: white;
    margin-bottom: 1.5rem;
}

/* ---------- INPUTS ---------- */

.input-row {
    margin-top: 0.5rem;
}

.stTextArea textarea,
.stTextInput input {
    border-radius: 14px !important;
    border: 1.5px solid #dbe2ea !important;
    background: #ffffff !important;
    color: #0f172a !important;

    padding: 14px !important;
    font-size: 15px !important;

    transition: all 0.2s ease;
}

.stTextArea textarea:focus,
.stTextInput input:focus {
    border-color: #6366f1 !important;
    box-shadow: 0 0 0 4px rgba(99,102,241,0.12) !important;
}

.stTextArea label,
.stTextInput label {
    font-weight: 600 !important;
    color: #334155 !important;
    margin-bottom: 0.5rem !important;
}

textarea {
    min-height: 180px !important;
}

/* ---------- BUTTON ---------- */

.stButton button {
    width: 100%;
    height: 56px;

    border: none !important;
    border-radius: 14px !important;

    background: linear-gradient(135deg, #6366f1, #8b5cf6) !important;

    color: white !important;
    font-size: 1rem !important;
    font-weight: 600 !important;

    margin-top: 1.8rem;

    transition: all 0.25s ease !important;
}

.stButton button:hover {
    transform: translateY(-2px);
    box-shadow: 0 14px 28px rgba(99,102,241,0.25);
}

/* ---------- SCORE SECTION ---------- */

.score-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 1.2rem;
    margin-top: 1.5rem;
}

.score-card {
    background: white;
    border-radius: 18px;
    padding: 1.5rem;

    border: 1px solid #e5e7eb;

    position: relative;
    overflow: hidden;

    transition: all 0.25s ease;

    box-shadow: 0 6px 22px rgba(15,23,42,0.05);
}

.score-card::before {
    content: "";
    position: absolute;

    top: 0;
    left: 0;

    width: 100%;
    height: 4px;

    background: var(--card-color);
}

.score-card:hover {
    transform: translateY(-4px);
    box-shadow: 0 18px 40px rgba(15,23,42,0.08);
}

.score-number {
    font-size: 2.8rem;
    font-weight: 700;
    line-height: 1;
    color: var(--card-color);
}

.score-label {
    margin-top: 0.7rem;
    font-size: 1rem;
    font-weight: 600;
    color: #334155;
}

.score-percentage {
    margin-top: 0.35rem;
    color: #64748b;
    font-size: 0.9rem;
}

/* ---------- FEEDBACK ---------- */

.feedback-section {
    margin-top: 2rem;
}

.feedback-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 1.2rem;
}

.feedback-item {
    background: white;
    border-radius: 18px;

    padding: 1.4rem;

    border: 1px solid #e5e7eb;
    border-left: 5px solid var(--feedback-color);

    box-shadow: 0 6px 22px rgba(15,23,42,0.05);
}

.feedback-title {
    font-size: 1rem;
    font-weight: 600;
    margin-bottom: 0.8rem;
    color: var(--feedback-color);
}

.feedback-text {
    font-size: 0.95rem;
    line-height: 1.7;
    color: #475569;
}

/* ---------- ALERTS ---------- */

.stSuccess,
.stError,
.stWarning {
    border-radius: 14px !important;
}

/* ---------- JSON ---------- */

.stJson {
    border-radius: 14px !important;
    overflow: hidden;
}

/* ---------- RESPONSIVE ---------- */

@media (max-width: 992px) {

    .score-grid,
    .feedback-grid {
        grid-template-columns: 1fr;
    }

    .main-title {
        font-size: 2.2rem;
    }
}

@media (max-width: 768px) {

    .block-container {
        padding-left: 1rem !important;
        padding-right: 1rem !important;
    }

    .main-container {
        padding: 1rem;
        border-radius: 18px;
    }

    .main-title {
        font-size: 2rem;
    }

    textarea {
        min-height: 140px !important;
    }

    .stButton button {
        margin-top: 0.5rem;
    }
}
</style>
""", unsafe_allow_html=True)

def get_score_color(score: int, max_score: int = 6) -> str:
    """Get color based on score percentage"""
    percentage = (score / max_score) * 100
    if percentage >= 80:
        return "#10b981"  # Green
    elif percentage >= 60:
        return "#f59e0b"  # Amber
    else:
        return "#ef4444"  # Red

def display_scores_section(result: Dict[Any, Any]):
    """Display all scores in a grid"""
    content_score = result.get("content_score", 0)
    structure_score = result.get("structure_score", 0)
    linguistic_score = result.get("linguistic_score", 0)
    
    # Get structure breakdown
    structure_points = result.get("structure_points", 0)
    coherence_points = result.get("coherence_points", 0)
    content_percentage = result.get("content_percentage", 0)
    
    content_color = get_score_color(content_score)
    structure_color = get_score_color(structure_score)
    linguistic_color = get_score_color(linguistic_score)
    linguitic_percentage = result.get("linguistic_percentage", 0)
    
    st.markdown(f"""
    <div class="score-grid">
        <div class="score-card" style="--card-color: {content_color};">
            <div class="score-number">{content_score}/6</div>
            <div class="score-label">Content</div>
            <div class="score-percentage">{content_percentage}% relevancy</div>
        </div>
        <div class="score-card" style="--card-color: {structure_color};">
            <div class="score-number">{structure_score}/6</div>
            <div class="score-label">Structure</div>
            <div class="score-percentage">Paragraphs: {structure_points}/4 | Coherence: {coherence_points}/2</div>
        </div>
        <div class="score-card" style="--card-color: {linguistic_color};">
            <div class="score-number">{linguistic_score}/6</div>
            <div class="score-label">Linguistic</div>
            <div class="score-percentage">{linguitic_percentage}%</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

def display_feedback_section(result: Dict[Any, Any]):
    """Display all feedback in a grid"""
    content_feedback = result.get("content_feedback", "No feedback available")
    structure_feedback = result.get("structure_feedback", "No feedback available")
    linguistic_feedback = result.get("linguistic_feedback", "No feedback available")
    
    content_color = get_score_color(result.get("content_score", 0))
    structure_color = get_score_color(result.get("structure_score", 0))
    linguistic_color = get_score_color(result.get("linguistic_score", 0))
    
    st.markdown(f"""
    <div class="feedback-section">
        <h3 style="margin-top: 0; color: #333; font-weight: 600;">📝 Detailed Feedback</h3>
        <div class="feedback-grid">
            <div class="feedback-item" style="--feedback-color: {content_color};">
                <div class="feedback-title">📖 Content Analysis</div>
                <div class="feedback-text">{content_feedback}</div>
            </div>
            <div class="feedback-item" style="--feedback-color: {structure_color};">
                <div class="feedback-title">🏗️ Structure Analysis</div>
                <div class="feedback-text">{structure_feedback}</div>
            </div>
            <div class="feedback-item" style="--feedback-color: {linguistic_color};">
                <div class="feedback-title">🗣️ Linguistic Analysis</div>
                <div class="feedback-text">{linguistic_feedback}</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

def call_essay_api(essay_prompt: str, essay_text: str, api_url: str, token: str) -> Dict[Any, Any]:
    """Call the essay scoring API"""
    payload = {
        "essay_prompt": essay_prompt,
        "essay_text": essay_text,
        "token": token
    }
    
    headers = {
        "Content-Type": "application/json",
        "X-API-TOKEN": token
    }
    
    try:
        response = requests.post(f"{api_url}/score-essay", json=payload, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"API Error: {str(e)}")
        return None

def main():
    st.markdown('<div class="main-container">', unsafe_allow_html=True)
    
    # Header section
    st.markdown("""
    <div class="header-section">
        <h1 class="main-title">🎯 Essay Scorer Pro</h1>
        <p class="subtitle">AI-powered essay analysis with instant scoring and feedback</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Configuration in a compact section
    with st.expander("⚙️ Configuration", expanded=False):
        api_url = st.text_input("API URL", value="https://la-model-proofreading-staging.languageacademy.com.au")
    
    # Hardcoded token - REPLACE WITH YOUR ACTUAL TOKEN
    api_token = "pte_lsahdpasdhfasdhfasuaosiudfg"  # Replace with your actual token
    
    # Input section - single row
    st.markdown('<div class="input-row">', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col1:
        essay_prompt = st.text_area(
            "📋 Essay Prompt",
            height=120,
            placeholder="Enter the essay topic or question..."
        )
    
    with col2:
        essay_text = st.text_area(
            "✍️ Student Essay",
            height=120,
            placeholder="Paste the complete essay text here..."
        )
    
    with col3:
        st.markdown("<br>", unsafe_allow_html=True)  # Spacing
        score_button = st.button("🚀 Analyze Essay", type="primary", use_container_width=True)
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Results section
    if score_button:
        if not essay_prompt.strip():
            st.error("⚠️ Please enter an essay prompt")
            return
        
        if not essay_text.strip():
            st.error("⚠️ Please enter the essay text")
            return
        
        # Show loading with progress
        with st.spinner("🔍 Analyzing essay content, structure, and language..."):
            result = call_essay_api(essay_prompt, essay_text, api_url, api_token)
        
        if result:
            # Success message
            st.success("✅ Analysis complete! Here are the results:")
            
            # Display scores section
            display_scores_section(result)
            
            # Display feedback section
            display_feedback_section(result)
            
            # Raw data toggle
            with st.expander("🔍 View Raw API Response"):
                st.json(result)
    
    st.markdown('</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()