import streamlit as st
import PyPDF2
from docx import Document
import os
import pandas as pd
import datetime
from gtts import gTTS
import io
import base64
import speech_recognition as sr
from io import BytesIO

# Configuration
CHUNK = 1024
RATE = 44100
RECORDING_FILE = "temp_recording.wav"

# Initialize session state
def init_session_state():
    if 'current_page' not in st.session_state:
        st.session_state.current_page = "verification"
    if 'interview_data' not in st.session_state:
        st.session_state.interview_data = {}
    if 'shortlisted_df' not in st.session_state:
        st.session_state.shortlisted_df = None
    if 'interviews' not in st.session_state:
        st.session_state.interviews = {}
    if 'current_question_index' not in st.session_state:
        st.session_state.current_question_index = 0
    if 'interview_started_processing' not in st.session_state:
        st.session_state.interview_started_processing = False
    if 'interview_processed_successfully' not in st.session_state:
        st.session_state.interview_processed_successfully = False
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'dynamic_questions' not in st.session_state:
        st.session_state.dynamic_questions = []
    if 'audio_question_played' not in st.session_state:
        st.session_state.audio_question_played = False
    if 'audio_file' not in st.session_state:
        st.session_state.audio_file = None
    if 'transcribed_text' not in st.session_state:
        st.session_state.transcribed_text = ""

def record_audio():
    """Simplified audio recording using file upload"""
    st.write("Record your answer using your device's voice recorder and upload it:")
    audio_file = st.file_uploader("Upload audio file", type=["wav", "mp3"], label_visibility="collapsed")
    
    if audio_file:
        st.audio(audio_file)
        return audio_file
    return None

def transcribe_audio(audio_file):
    """Transcribe audio using speech_recognition"""
    try:
        r = sr.Recognizer()
        
        # Save uploaded file to temporary location
        with open("temp_audio", "wb") as f:
            f.write(audio_file.getbuffer())
        
        with sr.AudioFile("temp_audio") as source:
            audio_data = r.record(source)
            text = r.recognize_google(audio_data)
            return text
    except sr.UnknownValueError:
        return "Could not understand audio"
    except sr.RequestError:
        return "Speech service error"
    except Exception as e:
        return f"Error: {str(e)}"

def text_to_speech(text, lang='en'):
    """Convert text to speech"""
    try:
        tts = gTTS(text=text, lang=lang, slow=False)
        audio_bytes = io.BytesIO()
        tts.write_to_fp(audio_bytes)
        audio_bytes.seek(0)
        return audio_bytes
    except Exception as e:
        st.error(f"TTS error: {str(e)}")
        return None

def play_audio(audio_bytes):
    """Play audio in Streamlit"""
    audio_base64 = base64.b64encode(audio_bytes.read()).decode('utf-8')
    audio_html = f"""
    <audio controls autoplay>
    <source src="data:audio/mp3;base64,{audio_base64}" type="audio/mp3">
    </audio>
    """
    st.components.v1.html(audio_html, height=50)

def extract_text_from_document(uploaded_file):
    """Extract text from PDF, DOCX, or TXT files"""
    try:
        if uploaded_file.name.lower().endswith(".pdf"):
            reader = PyPDF2.PdfReader(uploaded_file)
            return "".join(page.extract_text() for page in reader.pages if page.extract_text())
        elif uploaded_file.name.lower().endswith((".doc", ".docx")):
            doc = Document(uploaded_file)
            return "\n".join(para.text for para in doc.paragraphs)
        elif uploaded_file.name.lower().endswith(".txt"):
            return uploaded_file.read().decode("utf-8")
        else:
            st.warning("Unsupported file type")
            return ""
    except Exception as e:
        st.error(f"Error processing file: {str(e)}")
        return ""

def load_candidate_list(uploaded_file):
    """Load candidate list from Excel"""
    try:
        df = pd.read_excel(uploaded_file)
        if 'Name' not in df.columns:
            st.error("Excel file must contain a 'Name' column")
            return None
        if 'Job Description' not in df.columns:
            df['Job Description'] = ""
        return df
    except Exception as e:
        st.error(f"Error loading Excel file: {str(e)}")
        return None

def generate_questions(job_description):
    """Generate interview questions based on job description"""
    questions = [
        "Tell us about your relevant experience",
        "What are your strengths for this role?",
        "Why are you interested in this position?"
    ]
    
    if "developer" in job_description.lower():
        questions = [
            "Describe your experience with programming languages",
            "How do you approach debugging complex issues?",
            "Explain your experience with version control systems"
        ]
    elif "marketing" in job_description.lower():
        questions = [
            "Describe your experience with digital marketing campaigns",
            "How would you approach SEO for a new website?",
            "What metrics would you track for campaign success?"
        ]
    
    return questions

def evaluate_response(answer, question, job_description):
    """Evaluate candidate response"""
    score = min(10, max(1, len(answer) // 20))  # Basic scoring
    feedback = "Good response" if score > 5 else "Could be more detailed"
    return score, feedback

def verification_page():
    """Candidate verification page"""
    st.header("📝 Candidate Verification")
    
    with st.expander("Candidate Information", expanded=True):
        candidate_name = st.text_input("Full Name (as per application)")
        resume_file = st.file_uploader("Upload Your Resume/CV", 
                                     type=["pdf", "docx", "txt"],
                                     help="Accepted formats: PDF, DOCX, TXT")
    
    st.markdown("---")
    st.subheader("Recruiter Section")
    candidate_list = st.file_uploader("Upload Shortlisted Candidates (Excel)", 
                                    type=["xlsx"],
                                    help="Must contain 'Name' and 'Job Description' columns")
    
    if candidate_list and st.button("Load Candidate List"):
        st.session_state.shortlisted_df = load_candidate_list(candidate_list)
        if st.session_state.shortlisted_df is not None:
            st.success(f"Loaded {len(st.session_state.shortlisted_df)} candidates")
            st.dataframe(st.session_state.shortlisted_df.head())
    
    if st.button("Start Interview", type="primary"):
        if not candidate_name.strip():
            st.error("Please provide your full name")
        elif st.session_state.shortlisted_df is None:
            st.error("Candidate list not loaded")
        else:
            candidate_data = st.session_state.shortlisted_df[
                st.session_state.shortlisted_df['Name'].str.strip().str.lower() == candidate_name.strip().lower()
            ]
            
            if candidate_data.empty:
                st.error("Name not found in candidate list")
            elif not resume_file:
                st.error("Please upload your resume")
            else:
                resume_text = extract_text_from_document(resume_file)
                if not resume_text.strip():
                    st.error("Could not extract text from resume")
                else:
                    job_description = candidate_data['Job Description'].iloc[0] if 'Job Description' in candidate_data.columns else ""
                    
                    st.session_state.dynamic_questions = generate_questions(job_description)
                    st.session_state.interview_data = {
                        "candidate_name": candidate_name.strip(),
                        "jd": job_description.strip(),
                        "verification_text": resume_text.strip(),
                        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "qa": []
                    }
                    st.session_state.current_page = "interview"
                    st.rerun()

def interview_page():
    """Main interview page"""
    interview_data = st.session_state.interview_data
    st.header(f"Interview Session: {interview_data['candidate_name']}")
    st.markdown("---")
    
    if st.session_state.interview_processed_successfully:
        show_results()
    else:
        conduct_interview()

def show_results():
    """Show interview results"""
    st.subheader("✅ Interview Completed")
    st.write(f"**Candidate:** {st.session_state.interview_data['candidate_name']}")
    st.write(f"**Total Score:** {st.session_state.interview_data.get('total_score', 'N/A')}/30")
    
    for i, qa in enumerate(st.session_state.interview_data['qa'], 1):
        with st.expander(f"Question {i} - Score: {qa.get('score', 'N/A')}/10"):
            st.write(f"**Question:** {qa['question']}")
            st.write(f"**Your Answer:** {qa['answer']}")
            st.write(f"**Feedback:** {qa.get('feedback', 'None')}")
    
    if st.button("Return to Start"):
        st.session_state.current_page = "verification"
        st.rerun()

def conduct_interview():
    """Conduct the interview questions"""
    if st.session_state.current_question_index < len(st.session_state.dynamic_questions):
        current_question = st.session_state.dynamic_questions[st.session_state.current_question_index]
        
        # Display question with audio
        st.subheader(f"Question {st.session_state.current_question_index + 1}/{len(st.session_state.dynamic_questions)}")
        if not st.session_state.audio_question_played:
            question_audio = text_to_speech(current_question)
            if question_audio:
                st.write(f"**{current_question}**")
                play_audio(question_audio)
            st.session_state.audio_question_played = True
        else:
            st.write(f"**{current_question}**")
        
        # Answer section
        st.write("### Your Answer")
        
        # Option 1: Upload audio
        st.write("Option 1: Upload recorded answer")
        audio_file = record_audio()
        
        # Option 2: Type answer
        text_answer = st.text_area("Option 2: Type your answer here", 
                                 height=150,
                                 key=f"text_answer_{st.session_state.current_question_index}")
        
        # Submit handling
        if st.button("Submit Answer", type="primary"):
            final_answer = ""
            
            # Check if audio was uploaded
            if audio_file:
                with st.spinner("Transcribing audio..."):
                    transcription = transcribe_audio(audio_file)
                    if not transcription.startswith(("Could not", "Speech service", "Error")):
                        final_answer = transcription
            
            # Fall back to text answer if no usable audio
            if not final_answer and text_answer.strip():
                final_answer = text_answer.strip()
            
            if not final_answer:
                st.error("Please provide a valid answer")
            else:
                st.session_state.interview_data['qa'].append({
                    "question": current_question,
                    "answer": final_answer,
                    "audio_file": audio_file.name if audio_file else None
                })
                
                # Prepare for next question or finish
                st.session_state.current_question_index += 1
                st.session_state.audio_question_played = False
                st.session_state.audio_file = None
                st.session_state.transcribed_text = ""
                
                if st.session_state.current_question_index >= len(st.session_state.dynamic_questions):
                    process_interview_results()
                
                st.rerun()
    
    elif not st.session_state.interview_started_processing:
        process_interview_results()

def process_interview_results():
    """Process and score interview responses"""
    st.session_state.interview_started_processing = True
    st.info("Processing your interview results...")
    
    # Calculate scores
    total_score = 0
    for qa in st.session_state.interview_data['qa']:
        score, feedback = evaluate_response(qa['answer'], qa['question'], st.session_state.interview_data['jd'])
        qa['score'] = score
        qa['feedback'] = feedback
        total_score += score
    
    st.session_state.interview_data['total_score'] = total_score
    st.session_state.interviews[st.session_state.interview_data['candidate_name']] = st.session_state.interview_data
    st.session_state.interview_processed_successfully = True
    st.rerun()

def recruiter_dashboard():
    """Recruiter dashboard page"""
    if not st.session_state.authenticated:
        recruiter_login()
    else:
        show_recruiter_dashboard()

def recruiter_login():
    """Recruiter login page"""
    st.subheader("🔒 Recruiter Login")
    password = st.text_input("Enter password", type="password")
    
    if st.button("Login"):
        if password == os.getenv("RECRUITER_PASSWORD", "admin123"):
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Incorrect password")
    
    if st.button("Back to Main"):
        st.session_state.current_page = "verification"
        st.rerun()

def show_recruiter_dashboard():
    """Show recruiter dashboard"""
    st.header("📊 Recruiter Dashboard")
    
    if st.session_state.interviews:
        st.subheader("Completed Interviews")
        for candidate, data in st.session_state.interviews.items():
            with st.expander(f"{candidate} - {data.get('total_score', 'N/A')}/30"):
                st.write(f"Date: {data['timestamp']}")
                st.download_button(
                    label="Download Transcript",
                    data=format_transcript(data),
                    file_name=f"{candidate}_interview.txt",
                    mime="text/plain"
                )
    else:
        st.info("No interviews completed yet")
    
    if st.button("Logout"):
        st.session_state.authenticated = False
        st.session_state.current_page = "verification"
        st.rerun()

def format_transcript(interview_data):
    """Format interview data as text transcript"""
    transcript = f"Interview Transcript - {interview_data['candidate_name']}\n"
    transcript += f"Date: {interview_data['timestamp']}\n"
    transcript += f"Total Score: {interview_data.get('total_score', 'N/A')}/30\n\n"
    
    for i, qa in enumerate(interview_data['qa'], 1):
        transcript += f"Question {i}: {qa['question']}\n"
        transcript += f"Answer: {qa['answer']}\n"
        transcript += f"Score: {qa.get('score', 'N/A')}/10\n"
        transcript += f"Feedback: {qa.get('feedback', 'None')}\n\n"
    
    return transcript

# Main App
def main():
    init_session_state()
    st.title("AI Interview Portal")
    st.markdown("---")
    
    if st.session_state.current_page == "verification":
        verification_page()
    elif st.session_state.current_page == "interview":
        interview_page()
    elif st.session_state.current_page == "recruiter_dashboard":
        recruiter_dashboard()

if __name__ == "__main__":
    main()