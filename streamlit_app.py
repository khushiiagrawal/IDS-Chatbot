import streamlit as st
from app import ComplaintResolutionChatbot

# Page configuration
st.set_page_config(
    page_title="Customer Support Chat",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Initialize chatbot in session state
if 'chatbot' not in st.session_state:
    st.session_state.chatbot = ComplaintResolutionChatbot()

if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

# Logo and header in one line
col1, col2, col3 = st.columns([1, 2, 1])

with col1:
    # Display UPSIDA logo on the left
    try:
        st.image("logoo.png", use_column_width=True)
    except:
        st.info("🏢 UPSIDA")

with col2:
    st.markdown("## Complaint Resolution Chatbot")
    st.markdown("#### *AI-Powered Chatbot by UPSIDA* ")

with col3:
    # Display kratitech logo on the right
    try:
        st.image("kratitech.jpeg", width=130)
    except:
        st.info("🏢 KratiTech")
    

st.markdown("---")

# Input section
st.markdown("### 💬 Send your message")

with st.form(key="chat_form", clear_on_submit=True):
    user_input = st.text_area(
        label="",
        placeholder="Type your complaint, question, or 'check status COMP-XXXXXX'",
        key="user_message",
        label_visibility="collapsed",
        height=100
    )
    
    col1, col2, col3 = st.columns([2, 1, 2])
    with col2:
        submitted = st.form_submit_button("Send Message", use_container_width=True)

# Handle message
if submitted and user_input.strip():
    with st.spinner("🤖 Support Assistant is typing..."):
        try:
            reply = st.session_state.chatbot.get_response(user_input.strip())
            st.session_state.chat_history.append({"role": "user", "content": user_input.strip()})
            st.session_state.chat_history.append({"role": "bot", "content": reply})
            st.rerun()
        except Exception as e:
            st.error(f"❌ Something went wrong: {str(e)}")

# Conversation history
if st.session_state.chat_history:

    st.markdown("### 💬 Conversation History")
    
    for i, msg in enumerate(st.session_state.chat_history):
        if msg["role"] == "user":
            # User message - simple container
            st.info(f"**You:**\n\n{msg['content']}")
        else:
            # Bot message - simple container  
            st.success(f"**🤖 Support Assistant:**\n\n{msg['content']}")
    
    # Clear chat button

    col1, col2, col3 = st.columns([2, 1, 2])
    with col2:
        if st.button("Clear Chat", use_container_width=True):
            st.session_state.chatbot.clear_history()
            st.session_state.chat_history = []
            st.rerun()

else:
    # Welcome message

    st.markdown("#### Welcome to our Complaint Resolution Chatbot! We'll help you with any issues or concerns you may have.")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("• 📝 Registering new complaints")
        st.markdown("• 📊 Checking complaint status")
        st.markdown("• ❓ Answering your questions")
        st.markdown("• 🔄 Providing updates & solutions")
    
    with col2:
        st.info("💡 **Quick Tips:**\n\n To check status: *'check status COMP-XXXXXX'*\n\n Be specific about your issue for faster resolution")
    


# Footer
st.markdown("---")
st.caption("🔒 Your privacy is protected | 🤖 Powered by AI | 🌐 24/7 Support Available")
