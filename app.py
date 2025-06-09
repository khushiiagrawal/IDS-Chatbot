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
                # First, check if this is related to customer service at all
                relevance_check = self.model.generate_content(
                    f"""Analyze this customer message to determine if it's relevant to CUSTOMER SERVICE and SUPPORT.

                    RELEVANT customer service topics:
                    - Product/service complaints, issues, or problems
                    - Questions about YOUR products or services
                    - Account, billing, or payment issues
                    - Technical support for YOUR products
                    - How-to questions about YOUR products/services
                    - Order, delivery, or shipping inquiries
                    - Return, refund, or warranty requests
                    - Service setup or configuration help
                    - User account or login problems
                    
                    NOT RELEVANT (reject these):
                    - General knowledge questions (e.g., "what is MCP server", "explain blockchain")
                    - Weather, news, entertainment, or unrelated topics
                    - Technical definitions unrelated to your business
                    - Academic or educational queries
                    - Personal advice or general life questions
                    - Programming help unrelated to your product
                    - Random factual questions
                    
                    Customer message: {user_input}
                    
                    Respond with only: "RELEVANT" or "NOT_RELEVANT"
                    """
                ).text.strip()
                
                # If not relevant to customer service, politely redirect
                if "NOT_RELEVANT" in relevance_check.upper():
                    response_text = "I'm a customer service assistant designed to help with product issues, account problems, billing questions, and technical support. I can't assist with general knowledge questions or topics unrelated to our services. Please let me know if you have any questions about our products or need help with any service-related issues."
                    self.chat_history.append({"role": "bot", "content": response_text})
                    return response_text
                
                # If relevant, then detect if it's a complaint
                complaint_detection = self.model.generate_content(
                    f"""Analyze this customer service message and determine if it's a COMPLAINT or just a general inquiry about our products/services.

                    A COMPLAINT includes:
                    - Product not working, broken, or defective
                    - Service problems or poor experiences  
                    - Billing or payment issues
                    - Delivery or shipping problems
                    - Account or technical problems
                    - Dissatisfaction with products/services
                    - Something needs to be fixed or resolved
                    
                    NOT a complaint (general inquiry):
                    - Questions about product features or how to use them
                    - Information requests about services
                    - How-to questions or usage instructions
                    - General product information requests
                    - Casual greetings or thank you messages
                    
                    Customer message: {user_input}
                    
                    Respond with only: "COMPLAINT" or "INQUIRY"
                    """
                ).text.strip()
                
                # Generate response with solutions
                initial_response = self.model.generate_content(
                    f"""You are a customer service chatbot for a specific company/product. ALWAYS respond in the SAME language that the customer uses. If customer writes in Hindi, reply in Hindi. If customer writes in English, reply in English.
                    
                    IMPORTANT: You can ONLY help with topics related to YOUR company's products and services. Do NOT answer general knowledge questions, technical definitions unrelated to your business, or off-topic queries.
                    
                    Your role is to provide customer support for:
                    - Your company's products and services
                    - Technical problems with YOUR products
                    - Account, billing, or payment issues
                    - Product usage questions and how-to guides
                    - Service setup and configuration
                    - Order, delivery, and shipping inquiries
                    - Returns, refunds, and warranty support
                    
                    When helping customers:
                    1. FIRST: Try to provide immediate solutions or troubleshooting steps
                    2. Be empathetic and understanding
                    3. Ask clarifying questions about THEIR specific situation
                    4. Provide step-by-step instructions when needed
                    5. Stay focused on YOUR company's products/services
                    
                    Customer's message: {user_input}
                    
                    Provide helpful customer service assistance related to your company's products and services.
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
                    f"""You are continuing a customer service conversation to help with the customer's issue. ALWAYS respond in the SAME language the customer is using. 
                    
                    IMPORTANT: Stay focused ONLY on customer service topics related to YOUR company's products and services. Do NOT answer general knowledge questions, technical definitions unrelated to your business, or off-topic queries.
                    
                    Previous conversation context:
                    {self.chat_history[-4:] if len(self.chat_history) > 4 else self.chat_history}
                    
                    Current message: {user_input}
                    
                    Your goal is to SOLVE their customer service issue:
                    - Provide specific solutions and troubleshooting steps for YOUR products
                    - Ask clarifying questions about their specific situation with YOUR services
                    - Offer alternative approaches if the first solution doesn't work
                    - Guide them step-by-step through problem resolution
                    - Be patient and helpful with customer service matters
                    - If they ask off-topic questions, politely redirect to customer service topics
                    - Stay focused on solving THIS specific customer service problem
                    
                    If the customer asks something unrelated to customer service, politely say: "I'm here to help with customer service issues related to our products and services. Let's focus on resolving your original concern."
                    
                    Continue helping them resolve their customer service issue.
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