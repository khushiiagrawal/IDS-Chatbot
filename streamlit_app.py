import streamlit as st
from app import IDSChatbot

# Set page config
st.set_page_config(
    page_title="IDS Support Chatbot",
    page_icon="🛡️",
    layout="wide"
)

# Layout using columns for sidebar and chat area
sidebar, chat_area = st.columns([1, 3], gap="medium")

with sidebar:
    st.markdown("<div class='sidebar'>", unsafe_allow_html=True)
    st.title("Chat Controls")
    if st.button("Clear Chat History"):
        if "chatbot" in st.session_state:
            st.session_state.chatbot.clear_history()
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

with chat_area:
    st.title("IDS Support Chatbot")
    st.subheader("Welcome to the Intrusion Detection System Support Chatbot!")
    st.markdown("""
    I can help you with questions about:
    - **Network security monitoring**
    - **Intrusion detection systems**
    - **Security alerts and analysis**
    - **Best practices for IDS deployment**
    - **Troubleshooting common issues**
    """)

    # Initialize chatbot
    if "chatbot" not in st.session_state:
        st.session_state.chatbot = IDSChatbot()

    # Display chat messages
    for message in st.session_state.chatbot.get_chat_history():
        role = message["role"]
        if role == "user":
            st.markdown(
                f"<div style='display: flex; align-items: center; justify-content: flex-end; margin-bottom: 0.5rem;'>"
                f"<div style='background: linear-gradient(90deg, #3a8dde 0%, #005bea 100%); color: #fff; padding: 0.8rem 1.2rem; border-radius: 1rem; margin-left: 0.5rem; max-width: 70%;'>{message['content']}</div>"
                f"<span style='font-size:1.5rem; margin-left: 0.5rem;'>👤</span>"
                f"</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f"<div style='display: flex; align-items: center; margin-bottom: 0.5rem;'>"
                f"<span style='font-size:1.5rem; margin-right: 0.5rem;'>🤖</span>"
                f"<div style='background: #23272f; color: #e2e6ee; padding: 0.8rem 1.2rem; border-radius: 1rem; margin-right: 0.5rem; max-width: 70%;'>{message['content']}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

    # Chat input
    prompt = st.chat_input("Ask me anything about IDS systems...")
    if prompt:
        response = st.session_state.chatbot.get_response(prompt)
        st.rerun() 