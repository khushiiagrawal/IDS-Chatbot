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
        """Format ISO timestamp to Indian Standard Time"""
        from datetime import timezone, timedelta
        
        # Parse the UTC timestamp
        dt = datetime.fromisoformat(iso_timestamp.replace('Z', '+00:00'))
        
        # Convert to Indian Standard Time (UTC+5:30)
        ist = timezone(timedelta(hours=5, minutes=30))
        dt_ist = dt.replace(tzinfo=timezone.utc).astimezone(ist)
        
        return dt_ist.strftime("%B %d, %Y at %I:%M %p IST")

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

            # Handle manual resolution
            if any(phrase in user_input.lower() for phrase in ["mark as resolved", "issue is resolved", "problem is fixed", "it's working now", "it works now", "complaint is resolved", "resolved"]):
                # Check if user mentioned a specific complaint ID
                complaint_id_to_resolve = None
                words = user_input.split()
                for word in words:
                    if word.startswith("COMP-"):
                        complaint_id_to_resolve = word
                        break
                
                # Use mentioned complaint ID or current active one
                target_complaint_id = complaint_id_to_resolve or self.current_complaint_id
                
                if target_complaint_id:
                    # Verify the complaint exists
                    complaint = self.db.get_complaint(target_complaint_id)
                    if complaint:
                        self.db.update_complaint_status(
                            target_complaint_id, 
                            "Resolved",
                            f"Customer confirmed: {user_input}"
                        )
                        response_text = f"✅ Great news! I've updated complaint {target_complaint_id} status to 'Resolved'. Thank you for confirming that the issue has been fixed. Is there anything else I can help you with?"
                        self.chat_history.append({"role": "bot", "content": response_text})
                        return response_text
                    else:
                        response_text = f"I couldn't find complaint {target_complaint_id}. Please verify the complaint ID and try again."
                        self.chat_history.append({"role": "bot", "content": response_text})
                        return response_text
                else:
                    response_text = "I don't see an active complaint to mark as resolved. Please provide your complaint ID like: 'My complaint COMP-XXXXXX is resolved'."
                    self.chat_history.append({"role": "bot", "content": response_text})
                    return response_text

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
                                    role = "You" if msg[0] == "user" else "Support"
                                    response_text += f"\n{role}: {msg[1]}"
                            
                            self.chat_history.append({"role": "bot", "content": response_text})
                            return response_text
                        else:
                            response_text = "I couldn't find a complaint with that ID. Could you please verify the ID and try again?"
                            self.chat_history.append({"role": "bot", "content": response_text})
                            return response_text
                
                response_text = "To check your complaint status, please provide your complaint ID (it looks like COMP-20240315-xxxx)."
                self.chat_history.append({"role": "bot", "content": response_text})
                return response_text

            # Check if this is a new complaint or continuing conversation
            if not self.current_complaint_id:
                # First, detect if this is a complaint
                complaint_detection = self.model.generate_content(
                    f"""Analyze this customer message and determine if it's a COMPLAINT or just a general inquiry.

                    A COMPLAINT includes:
                    - Product not working, broken, or defective
                    - Service problems or poor experiences  
                    - Billing or payment issues
                    - Delivery or shipping problems
                    - Account or technical problems
                    - Dissatisfaction with products/services
                    - Something needs to be fixed or resolved
                    
                    NOT a complaint:
                    - General questions about products/services
                    - How-to questions or usage instructions
                    - Information requests
                    - Casual greetings
                    
                    Customer message: {user_input}
                    
                    Respond with only: "COMPLAINT" or "INQUIRY"
                    """
                ).text.strip()
                
                # Generate response with solutions
                initial_response = self.model.generate_content(
                    f"""You are a multilingual technical support chatbot that SOLVES customer problems and provides solutions. ALWAYS respond in the SAME language that the customer uses. If customer writes in Hindi, reply in Hindi. If customer writes in English, reply in English.
                    
                    Your primary goal is to HELP and SOLVE problems while also tracking them properly.
                    
                    When a customer has a problem:
                    1. FIRST: Try to provide immediate solutions, troubleshooting steps, or helpful information
                    2. SECOND: If you can't solve it immediately, guide them through step-by-step solutions
                    3. Be empathetic and understanding
                    4. Explain technical concepts in simple terms
                    
                    You can help with:
                    - Technical problems and troubleshooting
                    - Product usage questions and how-to guides
                    - Account issues and login problems
                    - Billing questions and payment issues
                    - Service setup and configuration
                    - General product information and features
                    - Step-by-step problem resolution
                    
                    Guidelines for helpful responses:
                    - Provide specific, actionable solutions
                    - Give step-by-step instructions when needed
                    - Ask clarifying questions to better understand the problem
                    - Offer multiple solution options when possible
                    - Be empathetic and understanding
                    
                    Customer's message: {user_input}
                    
                    Provide helpful solutions and assistance for their problem.
                    """
                ).text
                
                # Create complaint ID if this is a legitimate complaint
                if "COMPLAINT" in complaint_detection.upper():
                    self.current_complaint_id = self.db.add_complaint(user_input, initial_response)
                    response_text = initial_response + f"\n\nI've registered your concern with complaint ID: {self.current_complaint_id}. Please save this ID to check status or follow up on this issue anytime."
                else:
                    response_text = initial_response
            else:
                # This is a continuing conversation
                response = self.model.generate_content(
                    f"""You are continuing a multilingual technical support conversation to help solve the customer's problem. ALWAYS respond in the SAME language the customer is using. 
                    
                    Previous conversation context:
                    {self.chat_history[-4:] if len(self.chat_history) > 4 else self.chat_history}
                    
                    Current message: {user_input}
                    
                    Your goal is to SOLVE their problem, not just discuss it:
                    - Provide specific solutions and troubleshooting steps
                    - Ask clarifying questions to better understand their issue
                    - Offer alternative approaches if the first solution doesn't work
                    - Guide them step-by-step through problem resolution
                    - Be patient and helpful
                    - If they've tried your suggestions, offer more advanced solutions
                    - Only escalate to complaint registration if absolutely necessary
                    
                    Guidelines for helpful responses:
                    - Be solution-focused and actionable
                    - Provide clear, easy-to-follow instructions
                    - Show genuine understanding of their issue
                    - Offer multiple solution options when possible
                    - Use the same language they're communicating in
                    - Stay focused on solving THIS specific problem
                    
                    Continue helping them resolve their issue.
                    """
                )
                response_text = response.text

                # Check if the issue has been resolved based on the conversation
                resolution_check = self.model.generate_content(
                    f"""Analyze this conversation to determine if the customer's problem has been RESOLVED or is still ONGOING.

                    Customer's latest message: {user_input}
                    Support response: {response_text}
                    
                    Look for indicators that the problem is RESOLVED:
                    - Customer says it's working now, fixed, solved, resolved
                    - Customer thanks for the solution and confirms it worked
                    - Customer indicates the problem is no longer occurring
                    - Customer expresses satisfaction that the issue is resolved
                    
                    Look for indicators the problem is still ONGOING:
                    - Customer says it's still not working
                    - Customer needs more help or has follow-up questions
                    - Customer hasn't confirmed the solution worked
                    - Problem persists despite troubleshooting
                    
                    Respond with only: "RESOLVED" or "ONGOING"
                    """
                ).text.strip()

                # Add to conversation history in database
                self.db.add_to_conversation(self.current_complaint_id, "user", user_input)
                self.db.add_to_conversation(self.current_complaint_id, "bot", response_text)
                
                # Update complaint status if resolved
                if "RESOLVED" in resolution_check.upper():
                    self.db.update_complaint_status(
                        self.current_complaint_id, 
                        "Resolved",
                        f"Issue resolved through technical support assistance. Customer confirmed the solution worked."
                    )

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