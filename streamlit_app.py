import streamlit as st
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

API_URL = "https://la-model-proofreadorchestrator.languageacademy.com.au/score"

st.set_page_config(page_title="Writing Evaluator", layout="wide")
st.title("📝 Writing Evaluation Orchestrator")

# Test type selector
test_type = st.selectbox(
    "Select Test Type",
    ["summarize_spoken_text", "summarize_written_text"],
    index=0
)

passage = st.text_area("Enter Passage (Original text)", height=220, placeholder="Paste passage here...")
summary = st.text_area("Enter Student Summary", height=180, placeholder="Paste summary here...")

def build_highlighted_html(original_text, grammar_errors, mechanics_errors, spelling_errors, extra_space_errors, diffs):
    all_spans = []
    
    for error in grammar_errors:
        span = error.get("span")
        if span and span.get("start") is not None and span.get("end") is not None:
            if span["start"] <= span["end"]:
                all_spans.append({
                    "start": span["start"], "end": span["end"], "type": "grammar",
                    "message": error.get("message", error.get("type", "Grammar issue")),
                    "suggestion": error.get("corrected", ""),
                    "original": original_text[span["start"]:span["end"]]
                })
    
    for error in mechanics_errors:
        if isinstance(error, dict) and error.get("span"):
            span = error.get("span")
            if span["start"] <= span["end"]:
                all_spans.append({
                    "start": span["start"], "end": span["end"], "type": "grammar",
                    "message": error.get("message", error.get("type", "Mechanics issue")),
                    "suggestion": error.get("corrected", ""),
                    "original": original_text[span["start"]:span["end"]]
                })
    
    for word_info in spelling_errors:
        span = word_info.get("span")
        if span and span.get("start") < span.get("end"):
            all_spans.append({
                "start": span["start"], "end": span["end"], "type": "spelling",
                "message": "Spelling error",
                "suggestion": word_info.get("corrected", ""),
                "original": word_info.get("original", original_text[span["start"]:span["end"]])
            })
    
    for error in extra_space_errors:
        span = error.get("span")
        if span and span.get("start") < span.get("end"):
            all_spans.append({
                "start": span["start"], "end": span["end"], "type": "spacing",
                "message": "Extra space",
                "suggestion": error.get("corrected", ""),
                "original": error.get("original", original_text[span["start"]:span["end"]])
            })
    
    grammar_spelling_spans = set()
    for sp in all_spans:
        for i in range(sp["start"], sp["end"]):
            grammar_spelling_spans.add(i)
    
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
            "start": start, "end": end, "type": "vocabulary",
            "message": "Style suggestion", "suggestion": corrected,
            "original": original_text[start:end]
        })
    
    all_spans.sort(key=lambda x: (x["start"], -(x["end"] - x["start"])))
    filtered = []
    covered = set()
    
    for sp in all_spans:
        if any(i in covered for i in range(sp["start"], sp["end"])):
            continue
        filtered.append(sp)
        for i in range(sp["start"], sp["end"]):
            covered.add(i)
    
    filtered.sort(key=lambda x: x["start"], reverse=True)
    html = original_text
    
    for sp in filtered:
        if sp["start"] == sp["end"]:
            marker = f'<span style="background:#ffd6d6; padding:2px 4px; border-radius:4px; border:3px solid red; color:red;" title="{sp.get("suggestion", sp["message"])}" style="cursor:help;">⇧{sp.get("suggestion", "")}</span>'
            html = html[:sp["start"]] + marker + html[sp["start"]:]
            continue
        
        text_chunk = original_text[sp["start"]:sp["end"]]
        
        if sp["type"] == "grammar":
            border = "3px solid red"
            bg = "transparent"
        elif sp["type"] == "spelling":
            border = "3px solid #ff9800"
            bg = "transparent"
        elif sp["type"] == "spacing":
            border = "3px solid #9c27b0"
            bg = "transparent"
        else:
            border = "none"
            bg = "#fff2cc"
        
        suggestion = sp.get("suggestion", "").strip()
        message = sp.get("message", "Error")
        
        if suggestion:
            title = f"{message}\nChange to: {suggestion}"
        elif sp["type"] in ["grammar", "spacing", "mechanics"]:
            title = f"{message}\nRemove: '{text_chunk}'"
        else:
            title = message
        
        title = title.replace('"', '&quot;')
        marked = f'<span style="border:{border}; padding:2px 4px;border-radius:4px; background:{bg}; font-weight:500;" title="{title}">{text_chunk}</span>'
        html = html[:sp["start"]] + marked + html[sp["end"]:]
    
    return html, filtered

if st.button("Evaluate Writing"):
    if not passage.strip() or not summary.strip():
        st.warning("Passage and summary are required.")
    else:
        with st.spinner("Running orchestrator..."):
            resp = requests.post(
                API_URL,
                json={
                    "test_type": test_type,
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
        
        # For SST, show overall score summary first
        if test_type == "summarize_spoken_text":
            st.subheader("📊 Overall Score Summary")
            content_score = content.get("score", 0)
            form_score = form["score"]
            grammar_score = lang.get("scores", {}).get('grammar', 0)
            vocab_score = lang.get("scores", {}).get('vocabulary', 0)
            spelling_score = lang.get("scores", {}).get('spelling', 0)
            total_score = content_score + form_score + grammar_score + vocab_score + spelling_score
            
            col1, col2, col3, col4, col5, col6 = st.columns(6)
            col1.metric("Content", f"{content_score}/4")
            col2.metric("Form", f"{form_score}/2")
            col3.metric("Grammar", f"{grammar_score}/2")
            col4.metric("Vocabulary", f"{vocab_score}/2")
            col5.metric("Spelling", f"{spelling_score}/2")
            col6.metric("Total", f"{total_score}/12")
            
            st.divider()
        
        # Form Evaluation
        st.subheader("📋 Form Evaluation")
        col1, col2, col3 = st.columns([1, 1, 3])
        col1.metric("Form Score", form["score"])
        col2.metric("Word Count", form.get("word_count", 0))
        col3.info(form["feedback"])
        
        if form.get("issues"):
            st.markdown("**Form Issues:**")
            for issue in form["issues"]:
                st.error(issue)
        
        st.divider()
        
        # Content Evaluation
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
        
        st.markdown("**Content Feedback**")
        st.info(content.get("feedback", "No feedback available"))
        
        st.divider()
        
        # Language Evaluation
        st.subheader("✍️ Language Evaluation")
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader("📄 Summary (Highlighted)")
            html, all_errors = build_highlighted_html(
                lang.get("original", summary),
                lang.get("grammar_errors", []),
                lang.get("mechanics_errors", []),
                lang.get("spelling_errors", []),
                lang.get("extra_space_errors", []),
                lang.get("diffs", [])
            )
            st.markdown(f"<div style='font-size:16px;line-height:1.6'>{html}</div>", unsafe_allow_html=True)
            
            if lang.get("corrected"):
                st.subheader("✅ Corrected Summary")
                st.info(lang["corrected"])
        
        with col2:
            st.subheader("📊 Language Scores")
            scores = lang.get("scores", {})
            
            # Display scores based on test type
            if test_type == "summarize_spoken_text":
                s1, s2, s3 = st.columns(3)
                s1.metric("Spelling", f"{scores.get('spelling', 0)}/2")
                s2.metric("Grammar", f"{scores.get('grammar', 0)}/2")
                s3.metric("Vocabulary", f"{scores.get('vocabulary', 0)}/2")
            else:
                s1, s2 = st.columns(2)
                s1.metric("Grammar & Spelling", f"{scores.get('spelling_grammar_combined', 0)}")
                s2.metric("Vocabulary", f"{scores.get('vocabulary', 0)}")
            
            error_counts = lang.get('error_counts', {})
            grammar_count = error_counts.get('grammar', 0)
            spelling_count = error_counts.get('spelling', 0)
            spacing_count = error_counts.get('spacing', 0)
            vocab_count = error_counts.get('vocabulary', 0)
            total_count = error_counts.get('total', grammar_count + spelling_count + spacing_count + vocab_count)
            
            st.markdown("### Error Counts")
            st.write(f"🔴 Grammar: {grammar_count}")
            st.write(f"🟠 Spelling: {spelling_count}")
            st.write(f"🟣 Spacing: {spacing_count}")
            st.write(f"🟡 Vocabulary: {vocab_count}")
            st.write(f"**Total: {total_count}**")
            
            vocab_info = lang.get('vocabulary', {})
            if vocab_info.get('feedback'):
                st.markdown("### Vocabulary Feedback")
                st.info(vocab_info['feedback'])
            
            if grammar_count > 0:
                with st.expander(f"Grammar Errors ({grammar_count})"):
                    for e in lang.get("grammar_errors", []):
                        span = e.get("span", {})
                        if span and span.get("start") is not None and span.get("end") is not None:
                            orig_text = lang.get("original", summary)
                            orig = orig_text[span["start"]:span["end"]]
                            sug = e.get("corrected", "")
                            msg = e.get("message", "Grammar issue")
                            st.write(f"• Position {span['start']}-{span['end']}: '{orig}' → '{sug}' ({msg})")
                    
                    for m in lang.get("mechanics_errors", []):
                        if isinstance(m, dict):
                            span = m.get("span", {})
                            if span and span.get("start") is not None and span.get("end") is not None:
                                orig_text = lang.get("original", summary)
                                orig = m.get("original", orig_text[span["start"]:span["end"]] if orig_text else "")
                                sug = m.get("corrected", "")
                                msg = m.get("message", "Mechanics issue")
                                st.write(f"• Position {span['start']}-{span['end']}: '{orig}' → '{sug}' ({msg})")
            
            if spelling_count > 0:
                with st.expander(f"Spelling Errors ({spelling_count})"):
                    for w in lang.get("spelling_errors", []):
                        span = w.get("span", {})
                        if span and span.get("start") is not None and span.get("end") is not None:
                            orig_text = lang.get("original", summary)
                            orig = orig_text[span["start"]:span["end"]]
                            sug = w.get("corrected", "")
                            st.write(f"• Position {span['start']}-{span['end']}: '{orig}' → '{sug}'")
            
            if spacing_count > 0:
                with st.expander(f"Spacing Errors ({spacing_count})"):
                    for e in lang.get("extra_space_errors", []):
                        span = e.get("span", {})
                        if span and span.get("start") is not None and span.get("end") is not None:
                            orig = e.get("original", "")
                            sug = e.get("corrected", "")
                            st.write(f"• Position {span['start']}-{span['end']}: '{orig}' → '{sug}'")
            
            if vocab_count > 0:
                with st.expander(f"Vocabulary Suggestions ({vocab_count})"):
                    for diff in lang.get("diffs", []):
                        orig_span = diff.get("orig_span")
                        if orig_span and len(orig_span) >= 2:
                            orig = lang.get("original", summary)[orig_span[0]:orig_span[1]]
                            sug = diff.get("corrected", "")
                            st.write(f"• Position {orig_span[0]}-{orig_span[1]}: '{orig}' → '{sug}'")
        
        with st.expander("🔍 Raw JSON Response"):
            st.json(data)
