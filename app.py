import google.generativeai as genai
from dotenv import load_dotenv
import os
from complaint_db import ComplaintDatabase
from datetime import datetime

class ComplaintResolutionChatbot:
    def __init__(self):
        load_dotenv() 

        self.api_key = os.getenv('GOOGLE_API_KEY')
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY not found in environment variables")
        
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        self.chat_history = []
        self.db = ComplaintDatabase()
        self.current_complaint_id = None

    def format_timestamp(self, iso_timestamp):
        """Format ISO timestamp to a more readable format"""
        dt = datetime.fromisoformat(iso_timestamp)
        return dt.strftime("%B %d, %Y at %I:%M %p")

    def get_response(self, user_input):
        """
        Get a response from the chatbot for the given user input.
        
        Args:
            user_input (str): The user's complaint or message
            
        Returns:
            str: The chatbot's response
        """
        try:

            self.chat_history.append({"role": "user", "content": user_input})
            

            if "check status" in user_input.lower() or "complaint status" in user_input.lower():

                words = user_input.split()
                for word in words:
                    if word.startswith("COMP-"):
                        complaint = self.db.get_complaint(word)
                        if complaint:

                            conversation = self.db.get_conversation_history(word)
                            

                            response_text = f"I've found your complaint {word}.\n\n"
                            
              
                            status_emoji = {
                                "Open": "🔴",
                                "In Progress": "🟡",
                                "Resolved": "🟢"
                            }.get(complaint['status'], "⚪")
                            
                            response_text += f"Status: {status_emoji} {complaint['status']}\n"
                            response_text += f"Created: {self.format_timestamp(complaint['created_at'])}\n"
                            response_text += f"Last Updated: {self.format_timestamp(complaint['updated_at'])}\n"
                            
                            if complaint['resolution']:
                                response_text += f"\nResolution: {complaint['resolution']}\n"
                            
                
                            if conversation:
                                response_text += "\nRecent Updates:\n"

                                recent_messages = conversation[-3:] if len(conversation) > 3 else conversation
                                for msg in recent_messages:
                                    role = "You" if msg["role"] == "user" else "Support"
                                    response_text += f"\n{role}: {msg['content']}"
                            
                            self.chat_history.append({"role": "bot", "content": response_text})
                            return response_text
                        else:
                            response_text = "I couldn't find a complaint with that ID. Could you please verify the ID and try again?"
                            self.chat_history.append({"role": "bot", "content": response_text})
                            return response_text
                
                response_text = "To check your complaint status, please provide your complaint ID (it looks like COMP-20240315-xxxx)."
                self.chat_history.append({"role": "bot", "content": response_text})
                return response_text

       
            if not self.current_complaint_id:
        
                initial_response = self.model.generate_content(
                    f"""You are a helpful customer service chatbot. Respond to the customer's complaint in a natural, conversational way.
                    Guidelines:
                    - Be specific and direct
                    - Don't use generic templates or placeholders
                    - Show genuine understanding of their issue
                    - Provide clear, actionable next steps
                    - Keep the tone professional but friendly
                    - Don't make promises about specific timeframes unless absolutely certain
                    - Don't mention sending emails or making calls unless specifically requested
                    
                    Customer's message: {user_input}
                    
                    Respond as if you're a real customer service representative having a natural conversation.
                    """
                ).text
                
                self.current_complaint_id = self.db.add_complaint(user_input, initial_response)
                response_text = initial_response + f"\n\nI've registered your complaint with ID: {self.current_complaint_id}. Please save this ID for future reference."
            else:

                response = self.model.generate_content(
                    f"""You are continuing a customer service conversation. Previous messages:
                    {self.chat_history}
                    
                    Current message: {user_input}
                    
                    Guidelines:
                    - Be specific and direct
                    - Don't use generic templates or placeholders
                    - Show genuine understanding of their issue
                    - Provide clear, actionable next steps
                    - Keep the tone professional but friendly
                    - Don't make promises about specific timeframes unless absolutely certain
                    - Don't mention sending emails or making calls unless specifically requested
                    
                    Respond as if you're a real customer service representative having a natural conversation.
                    """
                )
                response_text = response.text
 
                self.db.add_to_conversation(self.current_complaint_id, "user", user_input)
                self.db.add_to_conversation(self.current_complaint_id, "bot", response_text)
            

            self.chat_history.append({"role": "bot", "content": response_text})
            
            return response_text
            
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
        self.current_complaint_id = None 