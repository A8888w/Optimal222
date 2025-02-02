import os
import logging
from datetime import datetime, timedelta

import streamlit as st
import arabic_reshaper
from bidi.algorithm import get_display

import fitz  # PyMuPDF for screenshot capture
import pdfplumber  # For searching text in PDF

from langchain_groq import ChatGroq
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_community.vectorstores import FAISS
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain.memory import ConversationBufferMemory
from langchain.prompts import PromptTemplate
from streamlit_mic_recorder import speech_to_text  # Speech-to-text function

# Configure logging
logging.basicConfig(level=logging.INFO)

# --- API Keys ---
# (For security, consider loading these from environment variables or a secure config file)
groq_api_key = "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"
google_api_key = "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"

# --- Streamlit page configuration ---
st.set_page_config(
    page_title="BGC ChatBot",
    page_icon="BGC Logo Colored.svg",
    layout="wide"
)

# --- Localization and UI texts ---
UI_TEXTS = {
    "العربية": {
        "page": "صفحة",
        "error_pdf": "حدث خطأ أثناء معالجة ملف PDF: ",
        "error_question": "حدث خطأ أثناء معالجة السؤال: ",
        "input_placeholder": "اكتب سؤالك هنا...",
        "source": "المصدر",
        "page_number": "صفحة رقم",
        "welcome_title": "بوت الدردشة BGC",
        "page_references": "مراجع الصفحات",
        "new_chat": "محادثة جديدة",
        "today": "اليوم",
        "yesterday": "أمس",
        "previous_chats": "سجل المحادثات",
        "welcome_message": """
**مرحبًا!**  
هذا بوت الدردشة الخاص بشركة غاز البصرة (BGC). يمكنك استخدام هذا البوت للحصول على معلومات حول الشركة وأنشطتها.  

**كيفية الاستخدام:**  
- اكتب سؤالك في الأسفل أو استخدم الميكروفون للتحدث.  
- سيتم الرد عليك بناءً على المعلومات المتاحة.  
"""
    },
    "English": {
        "page": "Page",
        "error_pdf": "Error processing PDF file: ",
        "error_question": "Error processing question: ",
        "input_placeholder": "Type your question here...",
        "source": "Source",
        "page_number": "Page number",
        "welcome_title": "BGC ChatBot",
        "page_references": "Page References",
        "new_chat": "New Chat",
        "today": "Today",
        "yesterday": "Yesterday",
        "previous_chats": "Chat History",
        "welcome_message": """
**Welcome!**  
This is the Basrah Gas Company (BGC) ChatBot. You can use this bot to get information about the company and its activities.  

**How to use:**  
- Type your question below or use the microphone to speak.  
- You will receive answers based on available information.  
"""
    }
}

# --- CSS for language direction ---
def apply_css_direction(direction):
    st.markdown(
        f"""
        <style>
            .stApp {{
                direction: {direction};
                text-align: {direction};
            }}
            .stChatInput {{
                direction: {direction};
            }}
            .stChatMessage {{
                direction: {direction};
                text-align: {direction};
            }}
        </style>
        """,
        unsafe_allow_html=True,
    )

# --- Arabic text normalization ---
def normalize_arabic_text(text):
    """
    Reshape and apply bidi algorithm to Arabic text so that it displays correctly.
    """
    try:
        reshaped = arabic_reshaper.reshape(text)
        return get_display(reshaped)
    except Exception as e:
        logging.error("Error normalizing Arabic text: %s", e)
        return text

# --- PDF Search and Screenshot Class ---
class PDFSearchAndDisplay:
    def __init__(self):
        self.fitz = fitz
        self.pdfplumber = pdfplumber

    def capture_screenshots(self, pdf_path, pages):
        """
        Capture screenshots for the specified pages.
        'pages' should be a list of tuples: (page_index, extra_info).
        Returns a list of image bytes.
        """
        screenshots = []
        try:
            doc = self.fitz.open(pdf_path)
            for page_num, _ in pages:
                if 0 <= page_num < len(doc):
                    page = doc[page_num]
                    # Convert page to image with a zoom factor for better resolution.
                    zoom = 2
                    mat = fitz.Matrix(zoom, zoom)
                    pix = page.get_pixmap(matrix=mat)
                    screenshots.append(pix.tobytes())
            doc.close()
        except Exception as e:
            st.error(f"{UI_TEXTS[interface_language]['error_pdf']}{str(e)}")
            logging.error("PDF screenshot capture error: %s", e)
        return screenshots

# --- Sidebar Configuration ---
with st.sidebar:
    # Language selection dropdown
    interface_language = st.selectbox("Interface Language", ["English", "العربية"])

    # Apply CSS based on language direction
    if interface_language == "العربية":
        apply_css_direction("rtl")
        st.title("الإعدادات")
    else:
        apply_css_direction("ltr")
        st.title("Settings")

    # Validate API key inputs and initialize components if valid
    if groq_api_key and google_api_key:
        os.environ["GOOGLE_API_KEY"] = google_api_key

        # Initialize ChatGroq with the provided API key and chosen model
        llm = ChatGroq(
            groq_api_key=groq_api_key, 
            model_name="oh-dcft-v3.1-claude-3-5-sonnet-20241022-GGUF"
        )

        # --- Chat Prompt Template (Language specific) ---
        def create_chat_prompt():
            if interface_language == "العربية":
                template = (
                    "أنت مساعد مفيد لشركة غاز البصرة (BGC). مهمتك هي الإجابة على الأسئلة بناءً على السياق المقدم حول BGC. اتبع هذه القواعد بدقة:\n\n"
                    "1. قدم إجابات دقيقة ومباشرة\n"
                    "2. استخدم فقط المعلومات من السياق المقدم\n"
                    "3. إذا لم تكن متأكداً، قل ذلك بصراحة\n"
                    "4. حافظ على لغة مهنية ومحترفة\n\n"
                    "السياق المقدم:\n"
                    "{context}\n\n"
                    "السؤال: {input}\n\n"
                    "تذكر أن تقدم إجابة:\n"
                    "1. دقيقة ومستندة إلى الوثائق\n"
                    "2. مباشرة وواضحة\n"
                    "3. مهنية ومنظمة"
                )
            else:
                template = (
                    "You are a helpful assistant for Basrah Gas Company (BGC). Answer the question based on the provided context. Follow these rules:\n\n"
                    "1. Provide accurate and direct answers.\n"
                    "2. Use only the provided context information.\n"
                    "3. If unsure, say so clearly.\n"
                    "4. Maintain a professional and organized tone.\n\n"
                    "Provided Context:\n"
                    "{context}\n\n"
                    "Question: {input}\n\n"
                    "Remember to provide an answer that is:\n"
                    "1. Accurate and document-based\n"
                    "2. Direct and clear\n"
                    "3. Professional and organized."
                )
            return PromptTemplate(template=template, input_variables=["context", "input"])

        def create_custom_chain(llm, prompt):
            return create_stuff_documents_chain(llm=llm, prompt=prompt)

        # --- Load Embeddings ---
        if "vectors" not in st.session_state:
            with st.spinner("جارٍ تحميل التضميدات... الرجاء الانتظار." if interface_language == "العربية" 
                            else "Loading embeddings... Please wait."):
                embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
                embeddings_path = "embeddings/Arabic/embeddings" if interface_language == "العربية" else "embeddings/English/embeddings"
                try:
                    st.session_state.vectors = FAISS.load_local(
                        embeddings_path, embeddings, allow_dangerous_deserialization=True
                    )
                except Exception as e:
                    error_msg = f"حدث خطأ أثناء تحميل التضميدات: {str(e)}" if interface_language == "العربية" else f"Error loading embeddings: {str(e)}"
                    st.error(error_msg)
                    logging.error("Embeddings load error: %s", e)
                    st.session_state.vectors = None

        # --- Voice Input ---
        st.markdown("### الإدخال الصوتي" if interface_language == "العربية" else "### Voice Input")
        input_lang_code = "ar" if interface_language == "العربية" else "en"
        voice_input = speech_to_text(
            start_prompt="🎤",
            stop_prompt="⏹️ إيقاف" if interface_language == "العربية" else "⏹️ Stop",
            language=input_lang_code,
            use_container_width=True,
            just_once=True,
            key="mic_button",
        )

        # --- Reset Chat Button ---
        if st.button("إعادة تعيين الدردشة" if interface_language == "العربية" else "Reset Chat"):
            st.session_state.messages = []
            st.session_state.chat_memories = {}
            st.success("تمت إعادة تعيين الدردشة بنجاح." if interface_language == "العربية" else "Chat has been reset successfully.")
            st.experimental_rerun()
    else:
        st.error("الرجاء إدخال مفاتيح API للمتابعة." if interface_language == "العربية" else "Please enter both API keys to proceed.")

# --- PDF Initialization ---
pdf_path = "BGC-Ar.pdf" if interface_language == "العربية" else "BGC.pdf"
pdf_searcher = PDFSearchAndDisplay()

# --- Main Chat Interface Header ---
col1, col2 = st.columns([1, 4])
with col1:
    st.image("BGC Logo Colored.svg", width=100)
with col2:
    st.title(UI_TEXTS[interface_language]['welcome_title'])
    st.write(UI_TEXTS[interface_language]['welcome_message'])

# --- Session State Initialization ---
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = {}
if 'current_chat_id' not in st.session_state:
    st.session_state.current_chat_id = None
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'chat_memories' not in st.session_state:
    st.session_state.chat_memories = {}

# --- Chat Management Functions ---
def create_new_chat():
    chat_id = datetime.now().strftime('%Y%m%d_%H%M%S')
    st.session_state.current_chat_id = chat_id
    st.session_state.messages = []
    st.session_state.chat_memories[chat_id] = ConversationBufferMemory(
        memory_key="history", return_messages=True
    )
    if chat_id not in st.session_state.chat_history:
        st.session_state.chat_history[chat_id] = {
            'messages': [],
            'timestamp': datetime.now(),
            'first_message': None,
            'visible': False
        }
    st.experimental_rerun()
    return chat_id

def update_chat_title(chat_id, message):
    if chat_id in st.session_state.chat_history:
        title = message.strip().replace('\n', ' ')
        title = title[:50] + '...' if len(title) > 50 else title
        st.session_state.chat_history[chat_id]['first_message'] = title
        st.experimental_rerun()

def load_chat(chat_id):
    if chat_id in st.session_state.chat_history:
        st.session_state.current_chat_id = chat_id
        st.session_state.messages = st.session_state.chat_history[chat_id]['messages']
        if chat_id not in st.session_state.chat_memories:
            st.session_state.chat_memories[chat_id] = ConversationBufferMemory(
                memory_key="history", return_messages=True
            )
            for msg in st.session_state.messages:
                if msg["role"] == "user":
                    st.session_state.chat_memories[chat_id].chat_memory.add_user_message(msg["content"])
                elif msg["role"] == "assistant":
                    st.session_state.chat_memories[chat_id].chat_memory.add_ai_message(msg["content"])
        st.experimental_rerun()

def format_chat_title(chat):
    display_text = chat['first_message'] or UI_TEXTS[interface_language]['new_chat']
    return display_text[:50] + '...' if len(display_text) > 50 else display_text

def format_chat_date(timestamp):
    today = datetime.now().date()
    chat_date = timestamp.date()
    if chat_date == today:
        return UI_TEXTS[interface_language]['today']
    elif chat_date == today - timedelta(days=1):
        return UI_TEXTS[interface_language]['yesterday']
    else:
        return timestamp.strftime('%Y-%m-%d')

# --- Sidebar Chat History ---
with st.sidebar:
    if st.button(UI_TEXTS[interface_language]['new_chat'], use_container_width=True):
        create_new_chat()
        st.experimental_rerun()

    st.markdown("---")
    st.markdown(f"### {UI_TEXTS[interface_language]['previous_chats']}")
    chats_by_date = {}
    for chat_id, chat_data in st.session_state.chat_history.items():
        if chat_data['visible'] and chat_data['messages']:
            date = chat_data['timestamp'].date()
            chats_by_date.setdefault(date, []).append((chat_id, chat_data))
    for date in sorted(chats_by_date.keys(), reverse=True):
        chats = chats_by_date[date]
        st.markdown(f"#### {format_chat_date(chats[0][1]['timestamp'])}")
        for chat_id, chat_data in sorted(chats, key=lambda x: x[1]['timestamp'], reverse=True):
            if st.sidebar.button(format_chat_title(chat_data), key=f"chat_{chat_id}", use_container_width=True):
                load_chat(chat_id)

# --- Display Page References with Normalization ---
def display_references(refs):
    """
    Display page references from the PDF.
    For Arabic, normalize the page number text.
    """
    if refs and isinstance(refs, dict) and "references" in refs:
        page_numbers = []
        for ref in refs["references"]:
            if "page" in ref and ref["page"] is not None:
                page_numbers.append(ref["page"])
        if page_numbers:
            with st.expander(UI_TEXTS[interface_language]["page_references"]):
                cols = st.columns(2)
                for idx, page_num in enumerate(sorted(set(page_numbers))):
                    # For Arabic, normalize the page number text (if it is a string)
                    if interface_language == "العربية":
                        display_page = normalize_arabic_text(str(page_num))
                    else:
                        display_page = str(page_num)
                    col_idx = idx % 2
                    with cols[col_idx]:
                        # Attempt to capture screenshot; if OCR-based extraction is needed,
                        # you could integrate Tesseract here as a fallback.
                        screenshots = pdf_searcher.capture_screenshots(pdf_path, [(page_num, "")])
                        if screenshots:
                            st.image(screenshots[0], use_container_width=True)
                        st.markdown(f"**{UI_TEXTS[interface_language]['page']} {display_page}**")

# --- Chat Message Display Functions ---
def display_chat_message(message, with_refs=False):
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if with_refs and "references" in message:
            display_references(message)

def display_response_with_references(response, answer):
    message = {
        "role": "assistant",
        "content": answer,
        "references": response.get("references", [])
    }
    display_chat_message(message, with_refs=True)

# --- Process User Input ---
def process_user_input(user_input, is_first_message=False):
    try:
        current_chat_id = st.session_state.current_chat_id
        current_memory = st.session_state.chat_memories.get(current_chat_id)
        user_message = {"role": "user", "content": user_input}
        st.session_state.messages.append(user_message)
        if is_first_message or (current_chat_id in st.session_state.chat_history and not st.session_state.chat_history[current_chat_id]['messages']):
            title = user_input.strip().replace('\n', ' ')
            title = title[:50] + '...' if len(title) > 50 else title
            st.session_state.chat_history[current_chat_id]['first_message'] = title
            st.session_state.chat_history[current_chat_id]['visible'] = True

        context = get_relevant_context(query=user_input)
        response = create_chat_response(user_input, context, current_memory, interface_language)
        assistant_message = {
            "role": "assistant",
            "content": response["answer"],
            "references": response.get("references", [])
        }
        st.session_state.messages.append(assistant_message)
        st.session_state.chat_history[current_chat_id]['messages'] = st.session_state.messages
        display_response_with_references(response, response["answer"])
        if is_first_message:
            st.experimental_rerun()
    except Exception as e:
        st.error(f"{UI_TEXTS[interface_language]['error_question']}{str(e)}")
        logging.error("Error in process_user_input: %s", e)

# --- Helper Functions for Context and Chat Response ---
def get_relevant_context(query, retriever=None):
    try:
        if retriever is None and "vectors" in st.session_state:
            retriever = st.session_state.vectors.as_retriever()
        if retriever:
            docs = retriever.get_relevant_documents(query)
            organized_context = []
            for doc in docs:
                organized_context.append({
                    "content": doc.page_content,
                    "page": doc.metadata.get("page", None),
                    "source": doc.metadata.get("source", None)
                })
            return {"references": organized_context}
        return {"references": []}
    except Exception as e:
        st.error(f"Error getting context: {str(e)}")
        logging.error("Error in get_relevant_context: %s", e)
        return {"references": []}

def create_chat_response(query, context, memory, language):
    try:
        references_text = ""
        if context and "references" in context:
            for ref in context["references"]:
                if ref["content"]:
                    references_text += f"\n{ref['content']}"
        # Determine response language based on query content
        if any('\u0600' <= char <= '\u06FF' for char in query):
            response_language = "Arabic"
            system_instruction = "You are a helpful assistant. Always respond in Arabic. Use the provided context to ensure accuracy."
        else:
            response_language = "English"
            system_instruction = "You are a helpful assistant. Always respond in English. Use the provided context to ensure accuracy."

        messages = []
        if references_text:
            messages.append({
                "role": "system",
                "content": f"{system_instruction} Use this context to answer the question:\n{references_text}"
            })
        if memory:
            chat_history = memory.load_memory_variables({})
            if "history" in chat_history:
                messages.extend(chat_history["history"])
        messages.append({"role": "user", "content": query})
        response = llm.invoke(messages)
        answer = response.content
        if memory:
            memory.chat_memory.add_user_message(query)
            memory.chat_memory.add_ai_message(answer)
        return {"answer": answer, "references": context.get("references", []) if context else []}
    except Exception as e:
        st.error(f"Error creating response: {str(e)}")
        logging.error("Error in create_chat_response: %s", e)
        return {"answer": UI_TEXTS[language].get('error_response', 'Error occurred.'), "references": []}

# --- Display Chat History ---
for message in st.session_state.messages:
    if message["role"] == "assistant" and "references" in message:
        display_chat_message(message, with_refs=True)
    else:
        display_chat_message(message)

# --- Text Chat Input ---
human_input = st.chat_input(UI_TEXTS[interface_language]['input_placeholder'])
if human_input:
    user_message = {"role": "user", "content": human_input}
    st.session_state.messages.append(user_message)
    is_first_message = len(st.session_state.messages) == 1
    if is_first_message:
        st.session_state.chat_history[st.session_state.current_chat_id]['first_message'] = human_input
    st.session_state.chat_history[st.session_state.current_chat_id]['messages'] = st.session_state.messages
    display_chat_message(user_message)
    process_user_input(human_input, is_first_message)

# --- Voice Input Handling ---
if voice_input:
    user_message = {"role": "user", "content": voice_input}
    st.session_state.messages.append(user_message)
    is_first_message = len(st.session_state.messages) == 1
    if is_first_message:
        st.session_state.chat_history[st.session_state.current_chat_id]['first_message'] = voice_input
    st.session_state.chat_history[st.session_state.current_chat_id]['messages'] = st.session_state.messages
    display_chat_message(user_message)
    process_user_input(voice_input, is_first_message)

# --- Create a New Chat if None Selected ---
if st.session_state.current_chat_id is None:
    create_new_chat()
