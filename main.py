import streamlit as st
import streamlit.components.v1 as components
from PIL import Image
import google.generativeai as genai
from dotenv import load_dotenv
import os
import io
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Image as ReportLabImage
from reportlab.lib.units import inch
from streamlit_webrtc import webrtc_streamer, WebRtcMode, VideoTransformerBase

# Load environment variables
load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

# Initialize session state
if 'history' not in st.session_state:
    st.session_state['history'] = []

if 'uploaded_image' not in st.session_state:
    st.session_state['uploaded_image'] = None

if 'tab' not in st.session_state:
    st.session_state['tab'] = 'New Chat'

if 'conversation_ids' not in st.session_state:
    st.session_state['conversation_ids'] = []

if 'current_conversation_id' not in st.session_state:
    st.session_state['current_conversation_id'] = None

if 'current_message_index' not in st.session_state:
    st.session_state['current_message_index'] = -1

# Function to load the new model and get responses
def get_gemini_response(input, image):
    model = genai.GenerativeModel('gemini-1.5-flash')  # Updated model name
    if input:
        if image:
            response = model.generate_content([input, image])
        else:
            response = model.generate_content([input])
    else:
        response = model.generate_content([image])
    return response.text

# Function to combine chat history for context
def get_combined_input():
    history = st.session_state['history']
    conversation_history = "\n".join([f"User: {chat['input']}\n\nBot: {chat['response']}" for chat in history[-3:]])
    return f"{conversation_history}\nUser: {st.session_state.input}"

# Function to handle input submission
def handle_submit():
    try:
        combined_input = get_combined_input()
        uploaded_image = st.session_state['uploaded_image']
        if combined_input.strip() or uploaded_image:
            response = get_gemini_response(combined_input, uploaded_image)
            st.session_state['history'].append({
                'input': st.session_state.input,
                'response': response,
                'image': uploaded_image
            })
            st.session_state.input = ""
            st.session_state.uploaded_image = None
            st.session_state['response'] = response
        else:
            st.error("Please provide either an input prompt or an image.")
    except Exception as e:
        st.error(f"An error occurred: {e}")

# Function to start a new chat
def start_new_chat():
    if st.session_state['history']:
        if st.session_state['current_conversation_id'] is None:
            conversation_id = len(st.session_state['conversation_ids']) + 1
        else:
            conversation_id = st.session_state['current_conversation_id']
        st.session_state[f'conversation_{conversation_id}'] = st.session_state['history'][:]
        if conversation_id not in st.session_state['conversation_ids']:
            st.session_state['conversation_ids'].append(conversation_id)
        st.session_state['history'] = []
        st.session_state['current_conversation_id'] = None
        st.session_state['current_message_index'] = -1

# Function to generate PDF
def generate_pdf():
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    story = []

    styles = getSampleStyleSheet()
    style_normal = styles['Normal']
    style_heading = ParagraphStyle(name='Heading', fontSize=14, fontName='Helvetica-Bold', spaceAfter=12)
    style_image = ParagraphStyle(name='Image', fontSize=12, spaceBefore=12, alignment=1)

    for chat in st.session_state['history']:
        # Input text
        input_paragraph = Paragraph(f"<b>User:</b> {chat['input']}", style_normal)
        story.append(input_paragraph)

        # Response text
        response_paragraph = Paragraph(f"<b>Bot:</b> {chat['response']}", style_normal)
        story.append(response_paragraph)

        # Add image if exists
        if chat['image']:
            image_path = f"temp_image_{len(st.session_state['history'])}.png"
            chat['image'].save(image_path)
            img = ReportLabImage(image_path, width=2*inch, height=2*inch)
            story.append(img)

        story.append(Paragraph("<br />", style_normal))  # Add a line break

    # Build PDF
    doc.build(story)
    buffer.seek(0)
    return buffer

# Webcam functionality
class VideoTransformer(VideoTransformerBase):
    def _init_(self):
        self.image = None

    def transform(self, frame):
        img = frame.to_ndarray(format="bgr24")
        self.image = img
        return img

    def capture_image(self):
        if self.image is not None:
            return Image.fromarray(self.image)
        return None

# Function to add a copy button next to the text
def copy_to_clipboard(question, answer, key):
    # JavaScript to copy to clipboard
    copy_button_html = f"""
    <style>
    .copy-btn {{
        background-color: #FF0000;
        border: none;
        color: white;
        padding: 8px 12px;
        text-align: center;
        text-decoration: none;
        display: inline-block;
        font-size: 14px;
        margin: 0;
        cursor: pointer;
        border-radius: 4px;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
        position: absolute;
        bottom: 10px;
        right: 10px;
    }}
    .copy-btn:hover {{
        background-color: #0056b3;
    }}
    </style>
    <script>
    function copyToClipboard_{key}() {{
        const el = document.createElement('textarea');
        el.value = User: {question}\\nBot: {answer};
        document.body.appendChild(el);
        el.select();
        document.execCommand('copy');
        document.body.removeChild(el);
        alert('Copied to clipboard');
    }}
    </script>
    <button class="copy-btn" onclick="copyToClipboard_{key}()">📋 Copy</button>
    """
    components.html(copy_button_html, height=50, width=100)

# Initialize the Streamlit app
st.set_page_config(page_title="PicTalk")

# Custom CSS for sidebar and footer
st.markdown(
    """
    <style>
    .sidebar-footer {
        position: fixed;
        bottom: 0;
        left: 0;
        width: 100%;
        padding: 10px;
        font-size: 16px;
        background-color: #808080;
        border-top: 1px solid #ddd;
        display: flex;
        justify-content: space-between;
        align-items: center;
        text-align: left;
    }
    .sidebar-footer .left {
        color: black;
    }
    .sidebar-footer .right {
        color: black;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Title at the top left
st.markdown("<h1 style='text-align: left;'>PicTalk</h1>", unsafe_allow_html=True)

col1, col2 = st.columns([2, 1])

# Sidebar for controls and history
with st.sidebar:
    # Add a white border at the bottom of the sidebar
    st.markdown(
        """
        <div class='sidebar-footer'>
            <div class='left'>Chat With PicTalk</div>
            <div class='right'>Developed By Team Debuggers</div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # Other sidebar components
    if st.button('💬Start New Chat'):
        start_new_chat()
        st.session_state['tab'] = 'New Chat'

    st.header("💾Saved Conversations")
    for conversation_id in st.session_state['conversation_ids']:
        if st.button(f"Conversation {conversation_id}"):
            st.session_state['tab'] = 'Chat History'
            st.session_state['history'] = st.session_state[f'conversation_{conversation_id}']
            st.session_state['current_conversation_id'] = conversation_id
            st.session_state['current_message_index'] = len(st.session_state['history']) - 1

    if st.button('🧹Clear History'):
        st.session_state['conversation_ids'] = []
        st.session_state['history'] = []
        st.write("Chat history cleared.")
    
    if st.button('📝Generate PDF'):
        pdf_buffer = generate_pdf()
        st.download_button(
            label="Download PDF",
            data=pdf_buffer,
            file_name="conversation_history.pdf",
            mime="application/pdf"
        )

# Main column for chat response or history
with col1:
    if st.session_state['tab'] == 'New Chat':
        # Display full chat history
        if st.session_state['history']:
            st.subheader("Chat History")
            for idx, chat in enumerate(st.session_state['history']):
                # Display the prompt and response
                st.write(f"Prompt {idx + 1}: {chat['input']}")
                st.write(f"Response {idx + 1}: {chat['response']}")

                # Display image if available
                if chat['image']:
                    st.image(chat['image'], caption=f"Image {idx + 1}", use_column_width=True)

                # Add the copy-to-clipboard button for both prompt and response
                copy_to_clipboard(chat['input'], chat['response'], idx + 1)
        else:
            st.subheader("Chat with me!")
            st.write("Start a new chat by entering a prompt or uploading an image.")
        
        # Input panel at the bottom of the main column
        input_container = st.container()
        with input_container:
            st.text_input("Input Prompt: ", key="input", on_change=handle_submit)
            uploaded_file = st.file_uploader("Choose an image...", type=["jpg", "jpeg", "png"], key="image_uploader")
            if uploaded_file is not None:
                image = Image.open(uploaded_file)
                st.session_state['uploaded_image'] = image
                st.image(image, caption="Uploaded Image.", use_column_width=True)
            
            # Move webcam capture functionality to a drawer
            with st.expander("Capture Image from Webcam", expanded=False):
                webrtc_ctx = webrtc_streamer(
                    key="webcam",
                    mode=WebRtcMode.SENDRECV,
                    video_transformer_factory=VideoTransformer
                )
                if st.button('Capture Webcam Image'):
                    if webrtc_ctx.video_transformer:
                        image = webrtc_ctx.video_transformer.capture_image()
                        if image:
                            st.session_state['uploaded_image'] = image
                            st.image(image, caption="Captured Webcam Image.", use_column_width=True)

    elif st.session_state['tab'] == 'Chat History':
        st.subheader("Chat History")
        if st.session_state['history']:
            for idx, chat in enumerate(st.session_state['history']):
                st.write(f"Prompt {idx + 1}: {chat['input']}")
                st.write(f"Response {idx + 1}: {chat['response']}")
                # Add copy to clipboard button
                copy_to_clipboard(chat['input'], chat['response'], idx + 1)