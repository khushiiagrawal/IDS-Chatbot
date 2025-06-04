import streamlit as st
from app import ComplaintResolutionChatbot


if 'chatbot' not in st.session_state:
    st.session_state.chatbot = ComplaintResolutionChatbot()


st.set_page_config(
    page_title="Complaint Resolution Chatbot",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="collapsed"
)


st.markdown("""
    <style>
    .stApp {
        max-width: 100%;
        padding: 0;
    }
    .main {
        padding: 0;
    }
    .stTextInput > div > div > input {
        border-radius: 20px;
        padding: 10px 20px;
    }
    .stButton > button {
        border-radius: 20px;
        padding: 10px 20px;
        background-color: #4CAF50;
        color: white;
    }
    .chat-message {
        padding: 1.5rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
        display: flex;
        flex-direction: column;
    }
    .chat-message.user {
        background-color: #2b313e;
    }
    .chat-message.bot {
        background-color: #475063;
    }
    .chat-message .content {
        display: flex;
        margin-top: 0.5rem;
    }
    .status-badge {
        display: inline-block;
        padding: 0.25rem 0.5rem;
        border-radius: 0.25rem;
        font-size: 0.875rem;
        font-weight: 500;
        margin-right: 0.5rem;
    }
    .status-open {
        background-color: #dc2626;
        color: white;
    }
    .status-progress {
        background-color: #d97706;
        color: white;
    }
    .status-resolved {
        background-color: #059669;
        color: white;
    }
    </style>
""", unsafe_allow_html=True)


st.title("💬 Complaint Resolution Chatbot")
st.markdown("""
    Welcome to our Complaint Resolution Chatbot! I'm here to help you with any issues or concerns you may have.
    
    You can:
    - Register a new complaint
    - Check the status of an existing complaint using your complaint ID
    - Get updates on your complaint resolution
    
    Just type your message below to get started!
""")


user_input = st.text_input("Type your message here...", key="user_input")


if st.button("Send"):
    if user_input:

        response = st.session_state.chatbot.get_response(user_input)

        st.experimental_rerun()


chat_history = st.session_state.chatbot.get_chat_history()
for message in chat_history:
    with st.container():
        if message["role"] == "user":
            st.markdown(f"""
                <div class="chat-message user">
                    <div class="content">
                        <div style="color: white;">{message["content"]}</div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
                <div class="chat-message bot">
                    <div class="content">
                        <div style="color: white;">{message["content"]}</div>
                    </div>
                </div>
            """, unsafe_allow_html=True)


if st.button("Clear Chat"):
    st.session_state.chatbot.clear_history()
    st.experimental_rerun() 