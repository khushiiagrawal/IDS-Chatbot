# IDS Support Chatbot

A customer support chatbot for Intrusion Detection Systems (IDS) built with Streamlit and Google's Gemini API.

## Features

- Modern, user-friendly chat interface
- Specialized in answering questions about Intrusion Detection Systems
- Real-time responses using Google's Gemini AI
- Persistent chat history during session
- Responsive design

## Setup Instructions

1. Clone this repository
2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Create a `.env` file in the root directory and add your Google API key:
   ```
   GOOGLE_API_KEY=your_api_key_here
   ```
   You can get your API key from the [Google AI Studio](https://makersuite.google.com/app/apikey)

4. Run the Streamlit app:
   ```bash
   streamlit run app.py
   ```

## Usage

1. Open your web browser and navigate to the URL shown in the terminal (usually http://localhost:8501)
2. Type your question about IDS systems in the chat input
3. The chatbot will respond with relevant information

## Example Questions

- What is an Intrusion Detection System?
- How does network-based IDS work?
- What are the best practices for IDS deployment?
- How to handle false positives in IDS?
- What's the difference between IDS and IPS?

## Note

Make sure to keep your API key secure and never commit it to version control. 