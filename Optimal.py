import streamlit as st
import os
from langchain_groq import ChatGroq
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.chains import create_retrieval_chain
from langchain_community.vectorstores import FAISS
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain.memory import ConversationBufferMemory
from streamlit_mic_recorder import speech_to_text  # Import speech-to-text function

# Initialize API key variables
groq_api_key = "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"
google_api_key = "AIzaSyDdAiOdIa2I28sphYw36Genb4D--2IN1tU"

# Change the page title and icon
st.set_page_config(
    page_title="BGC ChatBot",  # Page title
    page_icon="BGC Logo Colored.png",  # New page icon
    layout="wide"  # Page layout
)

# Function to apply CSS based on language direction
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

# Sidebar configuration
with st.sidebar:
    st.title("Settings")

    # Language selection dropdown
    interface_language = st.selectbox("Interface Language", ["English", "Arabic"])

    # Apply CSS direction based on selected language
    if interface_language == "Arabic":
        apply_css_direction("rtl")  # Right-to-left for Arabic
    else:
        apply_css_direction("ltr")  # Left-to-right for English

    # Validate API key inputs and initialize components if valid
    if groq_api_key and google_api_key:
        # Set Google API key as environment variable
        os.environ["GOOGLE_API_KEY"] = google_api_key

        # Initialize ChatGroq with the provided Groq API key
        llm = ChatGroq(groq_api_key=groq_api_key, model_name="gemma2-9b-it")

        # Define the chat prompt template with memory
        prompt = ChatPromptTemplate.from_messages([
            ("system", """
            You are a helpful assistant for Basrah Gas Company (BGC). Your task is to answer questions based on the provided context about BGC. Follow these rules strictly:

            1. **Language Handling:**
               - If the question is in English, answer in English.
               - If the question is in Arabic, answer in Arabic.
               - If the user explicitly asks for a response in a specific language, respond in that language.

            2. **Contextual Answers:**
               - Provide accurate and concise answers based on the context provided.
               - Do not explicitly mention the source of information unless asked.

            3. **Handling Unclear or Unanswerable Questions:**
               - If the question is unclear or lacks sufficient context, respond with:
                 - In English: "I'm sorry, I couldn't understand your question. Could you please provide more details?"
                 - In Arabic: "عذرًا، لم أتمكن من فهم سؤالك. هل يمكنك تقديم المزيد من التفاصيل؟"
               - If the question cannot be answered based on the provided context, respond with:
                 - In English: "I'm sorry, I don't have enough information to answer that question."
                 - In Arabic: "عذرًا، لا أملك معلومات كافية للإجابة على هذا السؤال."

            4. **User Interface Language:**
               - If the user has selected Arabic as the interface language, prioritize Arabic in your responses unless the question is explicitly in English.
               - If the user has selected English as the interface language, prioritize English in your responses unless the question is explicitly in Arabic.

            5. **Professional Tone:**
               - Maintain a professional and respectful tone in all responses.
               - Avoid making assumptions or providing speculative answers.
            """),
            MessagesPlaceholder(variable_name="history"),  # Add chat history to the prompt
            ("human", "{input}"),
            ("system", "Context: {context}"),
        ])

        # Load existing embeddings from files
        if "vectors" not in st.session_state:
            with st.spinner("Loading embeddings... Please wait." if interface_language == "English" else "جارٍ تحميل التضميدات... الرجاء الانتظار."):
                # Initialize embeddings
                embeddings = GoogleGenerativeAIEmbeddings(
                    model="models/embedding-001"
                )

                # Load existing FAISS index with safe deserialization
                embeddings_path = "embeddings"  # Path to your embeddings folder
                try:
                    st.session_state.vectors = FAISS.load_local(
                        embeddings_path,
                        embeddings,
                        allow_dangerous_deserialization=True  # Only use if you trust the source of the embeddings
                    )
                except Exception as e:
                    st.error(f"Error loading embeddings: {str(e)}" if interface_language == "English" else f"حدث خطأ أثناء تحميل التضميدات: {str(e)}")
                    st.session_state.vectors = None

        # Microphone button in the sidebar
        st.markdown("### Voice Input" if interface_language == "English" else "### الإدخال الصوتي")
        input_lang_code = "ar" if interface_language == "Arabic" else "en"  # Set language code based on interface language
        voice_input = speech_to_text(
            start_prompt="🎤",
            stop_prompt="⏹️ Stop" if interface_language == "English" else "⏹️ إيقاف",
            language=input_lang_code,  # Language (en for English, ar for Arabic)
            use_container_width=True,
            just_once=True,
            key="mic_button",
        )
    else:
        st.error("Please enter both API keys to proceed." if interface_language == "English" else "الرجاء إدخال مفاتيح API للمتابعة.")

# Main area for chat interface
# Use columns to display logo and title side by side
col1, col2 = st.columns([1, 4])  # Adjust the ratio as needed

# Display the logo in the first column
with col1:
    st.image("BGC Logo Colored.png", width=100)  # Adjust the width as needed

# Display the title and description in the second column
with col2:
    if interface_language == "Arabic":
        st.title("محمد الياسين | بوت الدردشة BGC")
        st.write("""
        **مرحبًا!**  
        هذا بوت الدردشة الخاص بشركة غاز البصرة (BGC). يمكنك استخدام هذا البوت للحصول على معلومات حول الشركة وأنشطتها.  
        **كيفية الاستخدام:**  
        - اكتب سؤالك في مربع النص أدناه.  
        - أو استخدم زر المايكروفون للتحدث مباشرة.  
        - سيتم الرد عليك بناءً على المعلومات المتاحة.  
        """)
    else:
        st.title("Mohammed Al-Yaseen | BGC ChatBot")
        st.write("""
        **Welcome!**  
        This is the Basrah Gas Company (BGC) ChatBot. You can use this bot to get information about the company and its activities.  
        **How to use:**  
        - Type your question in the text box below.  
        - Or use the microphone button to speak directly.  
        - You will receive a response based on the available information.  
        """)

# Initialize session state for chat messages if not already done
if "messages" not in st.session_state:
    st.session_state.messages = []

# Initialize memory if not already done
if "memory" not in st.session_state:
    st.session_state.memory = ConversationBufferMemory(
        memory_key="history",
        return_messages=True
    )

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# If voice input is detected, process it
if voice_input:
    st.session_state.messages.append({"role": "user", "content": voice_input})
    with st.chat_message("user"):
        st.markdown(voice_input)

    if "vectors" in st.session_state and st.session_state.vectors is not None:
        # Create and configure the document chain and retriever
        document_chain = create_stuff_documents_chain(llm, prompt)
        retriever = st.session_state.vectors.as_retriever()
        retrieval_chain = create_retrieval_chain(retriever, document_chain)

        # Get response from the assistant
        response = retrieval_chain.invoke({
            "input": voice_input,
            "context": retriever.get_relevant_documents(voice_input),
            "history": st.session_state.memory.chat_memory.messages  # Include chat history
        })
        assistant_response = response["answer"]

        # Append and display assistant's response
        st.session_state.messages.append(
            {"role": "assistant", "content": assistant_response}
        )
        with st.chat_message("assistant"):
            st.markdown(assistant_response)

        # Add user and assistant messages to memory
        st.session_state.memory.chat_memory.add_user_message(voice_input)
        st.session_state.memory.chat_memory.add_ai_message(assistant_response)

        # Display supporting information (page numbers only)
        with st.expander("Supporting Information" if interface_language == "English" else "المعلومات الداعمة"):
            if "context" in response:
                # Extract unique page numbers from the context
                page_numbers = set()
                for doc in response["context"]:
                    page_number = doc.metadata.get("page", "unknown")
                    if page_number != "unknown" and str(page_number).isdigit():  # Check if page_number is a valid number
                        page_numbers.add(int(page_number))  # Convert to integer for sorting

                # Display the page numbers
                if page_numbers:
                    page_numbers_str = ", ".join(map(str, sorted(page_numbers)))  # Sort pages numerically and convert back to strings
                    st.write(f"This answer is according to pages: {page_numbers_str}" if interface_language == "English" else f"هذه الإجابة وفقًا للصفحات: {page_numbers_str}")
                else:
                    st.write("No valid page numbers available in the context." if interface_language == "English" else "لا توجد أرقام صفحات صالحة في السياق.")
            else:
                st.write("No context available." if interface_language == "English" else "لا يوجد سياق متاح.")
    else:
        # Prompt user to ensure embeddings are loaded
        assistant_response = (
            "Embeddings not loaded. Please check if the embeddings path is correct." if interface_language == "English" else "لم يتم تحميل التضميدات. يرجى التحقق مما إذا كان مسار التضميدات صحيحًا."
        )
        st.session_state.messages.append(
            {"role": "assistant", "content": assistant_response}
        )
        with st.chat_message("assistant"):
            st.markdown(assistant_response)

# Text input field
if interface_language == "Arabic":
    human_input = st.chat_input("اكتب سؤالك هنا...")
else:
    human_input = st.chat_input("Type your question here...")

# If text input is detected, process it
if human_input:
    st.session_state.messages.append({"role": "user", "content": human_input})
    with st.chat_message("user"):
        st.markdown(human_input)

    if "vectors" in st.session_state and st.session_state.vectors is not None:
        # Create and configure the document chain and retriever
        document_chain = create_stuff_documents_chain(llm, prompt)
        retriever = st.session_state.vectors.as_retriever()
        retrieval_chain = create_retrieval_chain(retriever, document_chain)

        # Get response from the assistant
        response = retrieval_chain.invoke({
            "input": human_input,
            "context": retriever.get_relevant_documents(human_input),
            "history": st.session_state.memory.chat_memory.messages  # Include chat history
        })
        assistant_response = response["answer"]

        # Append and display assistant's response
        st.session_state.messages.append(
            {"role": "assistant", "content": assistant_response}
        )
        with st.chat_message("assistant"):
            st.markdown(assistant_response)

        # Add user and assistant messages to memory
        st.session_state.memory.chat_memory.add_user_message(human_input)
        st.session_state.memory.chat_memory.add_ai_message(assistant_response)

        # Display supporting information (page numbers only)
        with st.expander("Page References" if interface_language == "English" else "مراجع الصفحات"):
            if "context" in response:
                # Extract unique page numbers from the context
                page_numbers = set()
                for doc in response["context"]:
                    page_number = doc.metadata.get("page", "unknown")
                    if page_number != "unknown" and str(page_number).isdigit():  # Check if page_number is a valid number
                        page_numbers.add(int(page_number))  # Convert to integer for sorting

                # Display the page numbers
                if page_numbers:
                    page_numbers_str = ", ".join(map(str, sorted(page_numbers)))  # Sort pages numerically and convert back to strings
                    st.write(f"This answer is according to pages: {page_numbers_str}" if interface_language == "English" else f"هذه الإجابة وفقًا للصفحات: {page_numbers_str}")
                else:
                    st.write("No valid page numbers available in the context." if interface_language == "English" else "لا توجد أرقام صفحات صالحة في السياق.")
            else:
                st.write("No context available." if interface_language == "English" else "لا يوجد سياق متاح.")
    else:
        # Prompt user to ensure embeddings are loaded
        assistant_response = (
            "Embeddings not loaded. Please check if the embeddings path is correct." if interface_language == "English" else "لم يتم تحميل التضميدات. يرجى التحقق مما إذا كان مسار التضميدات صحيحًا."
        )
        st.session_state.messages.append(
            {"role": "assistant", "content": assistant_response}
        )
        with st.chat_message("assistant"):
            st.markdown(assistant_response)
