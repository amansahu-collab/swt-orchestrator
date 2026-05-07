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
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
    
    .stApp {
        background: #f8fafc;
        font-family: 'Inter', sans-serif;
    }
    
    .main-container {
        background: white;
        border-radius: 20px;
        padding: 2rem;
        margin: 1rem;
        box-shadow: 0 20px 60px rgba(0,0,0,0.08);
        border: 1px solid #e2e8f0;
    }
    
    .header-section {
        text-align: center;
        margin-bottom: 2rem;
    }
    
    .main-title {
        font-size: 2.5rem;
        font-weight: 700;
        background: linear-gradient(135deg, #667eea, #764ba2);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
    }
    
    .subtitle {
        color: #666;
        font-size: 1.1rem;
        margin-bottom: 2rem;
    }
    
    .score-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 1.5rem;
        margin: 2rem 0;
    }
    
    .score-card {
        background: white;
        border-radius: 15px;
        padding: 1.5rem;
        text-align: center;
        box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        border: 2px solid #f0f0f0;
        transition: all 0.3s ease;
        position: relative;
        overflow: hidden;
    }
    
    .score-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 4px;
        background: var(--card-color);
    }
    
    .score-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 20px 40px rgba(0,0,0,0.15);
    }
    
    .score-number {
        font-size: 3rem;
        font-weight: 700;
        color: var(--card-color);
        margin: 0;
        line-height: 1;
    }
    
    .score-label {
        font-size: 1rem;
        color: #666;
        margin-top: 0.5rem;
        font-weight: 600;
    }
    
    .score-percentage {
        font-size: 0.9rem;
        color: #999;
        margin-top: 0.3rem;
    }
    
    .feedback-section {
        background: white;
        border-radius: 15px;
        padding: 1.5rem;
        margin-top: 2rem;
        box-shadow: 0 10px 30px rgba(0,0,0,0.1);
    }
    
    .feedback-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 1.5rem;
    }
    
    .feedback-item {
        background: #f8f9fa;
        border-radius: 10px;
        padding: 1.2rem;
        border-left: 4px solid var(--feedback-color);
    }
    
    .feedback-title {
        font-weight: 600;
        color: var(--feedback-color);
        margin-bottom: 0.8rem;
        font-size: 1rem;
    }
    
    .feedback-text {
        color: #555;
        line-height: 1.5;
        font-size: 0.9rem;
    }
    
    .input-row {
        display: grid;
        grid-template-columns: 1fr 2fr 200px;
        gap: 1.5rem;
        align-items: end;
        margin-bottom: 2rem;
    }
    
    .stTextArea textarea, .stTextInput input {
        border-radius: 10px !important;
        border: 2px solid #e0e0e0 !important;
        font-family: 'Inter', sans-serif !important;
        background: white !important;
        color: #1a202c !important;
    }
    
    .stTextArea label, .stTextInput label {
        color: #2d3748 !important;
        font-weight: 600 !important;
    }
    
    .stButton button {
        background: linear-gradient(135deg, #667eea, #764ba2) !important;
        color: white !important;
        border: none !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
        padding: 0.7rem 2rem !important;
        font-size: 1rem !important;
        transition: all 0.3s ease !important;
    }
    
    .stButton button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 10px 25px rgba(102, 126, 234, 0.3) !important;
    }
    
    .stSpinner > div {
        color: #667eea !important;
    }
    
    .stSuccess {
        background: #f0fff4 !important;
        color: #22543d !important;
        border: 1px solid #9ae6b4 !important;
    }
    
    .stError {
        background: #fed7d7 !important;
        color: #742a2a !important;
        border: 1px solid #fc8181 !important;
    }
    
    .config-section {
        background: #f8f9fa;
        border-radius: 10px;
        padding: 1rem;
        margin-bottom: 1rem;
    }
    
    .stExpander {
        background: white !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 10px !important;
    }
    
    .stExpander > div > div {
        color: #2d3748 !important;
    }
    
    .stAlert {
        background: white !important;
        color: #2d3748 !important;
        border-radius: 10px !important;
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
            <div class="score-percentage">{(linguistic_score/6*100):.0f}%</div>
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