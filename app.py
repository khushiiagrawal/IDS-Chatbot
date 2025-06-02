import google.generativeai as genai
from dotenv import load_dotenv
import os

class IDSChatbot:
    def __init__(self):
        # Load environment variables
        load_dotenv()
        
        # Configure the Gemini API
        self.api_key = os.getenv('GOOGLE_API_KEY')
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY not found in environment variables")
        
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        self.chat_history = []

    def get_response(self, user_input):
        """
        Get a response from the chatbot for the given user input.
        
        Args:
            user_input (str): The user's question or message
            
        Returns:
            str: The chatbot's response
        """
        try:
            # Add user message to history
            self.chat_history.append({"role": "user", "content": user_input})
            
            # Generate response
            response = self.model.generate_content(
                f"""You are a helpful customer support chatbot specializing in Intrusion Detection Systems (IDS). 
                Provide clear, accurate, and professional responses to the following question: {user_input}
                Keep your response concise and focused on IDS-related information."""
            )
            
            # Add bot response to history
            self.chat_history.append({"role": "bot", "content": response.text})
            
            return response.text
            
        except Exception as e:
            error_message = f"An error occurred: {str(e)}"
            self.chat_history.append({"role": "bot", "content": error_message})
            return error_message

    def get_chat_history(self):
        """
        Get the current chat history.
        
        Returns:
            list: List of dictionaries containing chat messages
        """
        return self.chat_history

    def clear_history(self):
        """
        Clear the chat history.
        """
        self.chat_history = [] 