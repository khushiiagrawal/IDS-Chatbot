import google.generativeai as genai
from dotenv import load_dotenv
import os
from complaint_db import ComplaintDatabase
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
import re

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
        # Store user info in session
        self.user_info = {'name': None, 'mobile': None, 'address': None}
        self.complaint_state = 'idle'  # idle, awaiting_info, open, escalation_pending, resolved
        self.last_complaint_message = None
        self.clarification_turns = 0

    def format_timestamp(self, iso_timestamp):
        """Format ISO timestamp to Indian Standard Time"""
        from datetime import timezone, timedelta
        
        # Parse the UTC timestamp
        dt = datetime.fromisoformat(iso_timestamp.replace('Z', '+00:00'))
        
        # Convert to Indian Standard Time (UTC+5:30)
        ist = timezone(timedelta(hours=5, minutes=30))
        dt_ist = dt.replace(tzinfo=timezone.utc).astimezone(ist)
        
        return dt_ist.strftime("%B %d, %Y at %I:%M %p IST")

    def send_complaint_email(self, name, mobile, address, complaint, complaint_id):
        sender_email = os.getenv('SENDER_EMAIL')
        sender_password = os.getenv('SENDER_PASSWORD')
        recipient_email = 'khushisaritaagrawal@gmail.com'
        subject = f'New Complaint Registered: {complaint_id}'
        body = f"""
Name: {name}
Mobile: {mobile}
Address: {address}
Complaint: {complaint}
Complaint ID: {complaint_id}
"""
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = sender_email
        msg['To'] = recipient_email
        try:
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                server.login(sender_email, sender_password)
                server.send_message(msg)
        except Exception as e:
            print(f"Failed to send email: {e}")

    def extract_user_info(self, user_input):
        # Extract mobile number (10+ digits)
        mobile_match = re.search(r'(\d{10,})', user_input)
        if mobile_match:
            self.user_info['mobile'] = mobile_match.group(1)
        # Extract name
        name_match = re.search(r'(?:my name is|name is|name)\s*([a-zA-Z ]+)', user_input, re.IGNORECASE)
        if name_match:
            self.user_info['name'] = name_match.group(1).strip().replace(',', '')
        elif 'name' in user_input.lower() and not self.user_info['name']:
            # Try to get name before 'number' or 'mobile'
            parts = re.split(r'number|mobile', user_input, flags=re.IGNORECASE)
            if len(parts) > 1:
                self.user_info['name'] = parts[0].replace('name', '').replace(':', '').strip().replace(',', '')
        # Improved address extraction: capture everything after 'address:' or 'address is' or 'adderss' or at the end
        address_match = re.search(r'(?:address is|adderss is|address:|adderss:|address|adderss)\s*([a-zA-Z0-9 ,\-/]+)', user_input, re.IGNORECASE)
        if address_match:
            self.user_info['address'] = address_match.group(1).strip()
        elif 'address' in user_input.lower() or 'adderss' in user_input.lower():
            # Try to get address after number
            parts = re.split(r'number\s*\d{10,}', user_input, flags=re.IGNORECASE)
            if len(parts) > 1:
                self.user_info['address'] = parts[1].replace('address', '').replace('adderss', '').replace(':', '').strip().replace(',', '')
        # Fallback: if message has 3 comma-separated values, guess order
        if ',' in user_input and (not self.user_info['name'] or not self.user_info['mobile'] or not self.user_info['address']):
            parts = [p.strip() for p in user_input.split(',')]
            for part in parts:
                if not self.user_info['name'] and part.lower().startswith('my name'):
                    self.user_info['name'] = part.split()[-1]
                elif not self.user_info['mobile'] and re.search(r'\d{10,}', part):
                    self.user_info['mobile'] = re.search(r'\d{10,}', part).group(0)
                elif not self.user_info['address'] and ('address' in part.lower() or 'adderss' in part.lower()):
                    # Take everything after 'address' or 'adderss'
                    addr = re.split(r'address|adderss', part, flags=re.IGNORECASE)[-1]
                    self.user_info['address'] = addr.replace(':', '').strip()
                elif not self.user_info['address'] and not self.user_info['mobile'] and not self.user_info['name']:
                    # If only one left, treat as address
                    self.user_info['address'] = part

    def is_new_topic(self, new_msg, last_msg):
        if not last_msg:
            return True
        # If the new message is a clear new question (starts with 'what', 'how', 'why', etc.) and shares very few words, treat as new topic
        question_words = ['what', 'how', 'why', 'where', 'when', 'who']
        new_words = set(new_msg.lower().split())
        last_words = set(last_msg.lower().split())
        shared = new_words & last_words
        if any(new_msg.lower().startswith(qw) for qw in question_words) and len(shared) / max(1, len(new_words | last_words)) < 0.2:
            return True
        return False

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
            # Always try to extract user info from the latest message
            self.extract_user_info(user_input)

            # Improved topic change detection: only reset if the new message is truly unrelated
            if self.is_new_topic(user_input, self.last_complaint_message):
                self.last_complaint_message = user_input
                self.complaint_state = 'idle'
                self.clarification_turns = 0
                self.user_info = {'name': None, 'mobile': None, 'address': None}

            # Only set the complaint message if it is not already set and the message is not just user info
            info_keywords = ['name', 'mobile', 'number', 'address', 'adderss']
            if self.last_complaint_message is None and not all(kw in user_input.lower() for kw in info_keywords):
                self.last_complaint_message = user_input
                self.clarification_turns = 0  # Reset on new complaint

            # When generating a response, always pass the last few turns of conversation as context
            conversation_context = ''
            for msg in self.chat_history[-6:]:
                role = 'User' if msg['role'] == 'user' else 'Assistant'
                conversation_context += f"{role}: {msg['content']}\n"

            if self.complaint_state in ['idle', 'open', 'awaiting_info'] and self.last_complaint_message:
                # Use Gemini to try to resolve the complaint
                solution_response = self.model.generate_content(
                    f"""You are a support assistant. You do not answer topics which are not related to complaints or any problems. Always reply in the same language as the user's last message. If the user writes in Hindi, reply in Hindi. If the user writes in English, reply in English.\nWhen a user asks a question or makes a request, always provide a direct, helpful answer, best practices, or a typical list of requirements based on your general knowledge—even if you don't have all the specifics. If you don't have enough information for a specific answer, always provide a general, practical tip or best-practice suggestion for the topic at hand. Never just say you need more info—always give a helpful tip or next step. After your answer, always add: 'If you would like me to register and escalate this complaint to the higher authorities, please let me know and provide your name, mobile number, and address.' Only escalate automatically if it is absolutely necessary or the user specifically asks for escalation or says the problem is unresolved. If escalation is needed, respond with only: 'ESCALATE'.\n\nConversation so far:\n{conversation_context}\n"""
                ).text.strip()
                clarification_phrases = ['more information', 'please provide', 'could you tell me', 'i need some more information', 'to help me assist you better']
                is_clarification = any(phrase in solution_response.lower() for phrase in clarification_phrases)
                if solution_response == 'ESCALATE':
                    self.complaint_state = 'escalation_pending'
                    self.clarification_turns = 0  # Reset on escalation
                elif is_clarification:
                    self.clarification_turns += 1
                    if self.clarification_turns > 1:
                        self.complaint_state = 'escalation_pending'
                        self.clarification_turns = 0
                        # Use Gemini to generate a general summary/next step for the current context
                        summary_response = self.model.generate_content(
                            f"""Given the following conversation, provide a general next step, helpful tip, or best-effort answer for the user's issue, even if you don't have all the specifics. Do NOT mention any specific industry or problem unless the user did.\n\nConversation so far:\n{conversation_context}\n"""
                        ).text.strip()
                        self.chat_history.append({"role": "bot", "content": summary_response})
                        return summary_response
                    else:
                        self.complaint_state = 'open'
                        self.chat_history.append({"role": "bot", "content": solution_response})
                        return solution_response
                else:
                    self.complaint_state = 'open'
                    self.clarification_turns = 0
                    self.chat_history.append({"role": "bot", "content": solution_response})
                    return solution_response

            # If all user info is present and the user has provided a complaint description/location, log and escalate immediately
            if (self.user_info['name'] and self.user_info['mobile'] and self.user_info['address'] and self.last_complaint_message and self.complaint_state == 'escalation_pending'):
                self.current_complaint_id = self.db.add_complaint(self.last_complaint_message, "Complaint registered and escalated.")
                self.send_complaint_email(
                    self.user_info['name'],
                    self.user_info['mobile'],
                    self.user_info['address'],
                    self.last_complaint_message,
                    self.current_complaint_id
                )
                response_text = (
                    f"Thank you for providing the details. Your complaint has been registered and escalated for further help.\n\n"
                    f"Complaint ID: {self.current_complaint_id}\n"
                    f"Name: {self.user_info['name']}\n"
                    f"Mobile: {self.user_info['mobile']}\n"
                    f"Address: {self.user_info['address']}\n"
                    f"Complaint: {self.last_complaint_message}\n"
                    "We have also informed the concerned authority at khushisaritaagrawal@gmail.com for further action. "
                    "You will be updated on the progress."
                )
                self.complaint_state = 'resolved'
                self.chat_history.append({"role": "bot", "content": response_text})
                return response_text

            # Always check for missing user info before escalation or logging
            if self.complaint_state == 'escalation_pending':
                missing = []
                if not self.user_info['name']:
                    missing.append('name')
                if not self.user_info['mobile']:
                    missing.append('mobile number')
                if not self.user_info['address']:
                    missing.append('address')
                if missing:
                    return ("To log and escalate your complaint, please provide the following details in one message: "
                            + ', '.join(missing) + ". (e.g., 'My name is Rahul Sharma, my mobile number is 9876543210, my address is 123 Main Street, Kanpur')\n"
                            "Once I have this information, I will register your complaint, provide you with a complaint ID, and notify the concerned authority.")

            # If in the middle of a complaint, maintain context
            if self.complaint_state in ['awaiting_info', 'open', 'escalation_pending']:
                # Use LLM to check if more info is needed, escalation is needed, or resolved
                state_check = self.model.generate_content(
                    f"""Analyze this conversation and the latest user message.\n\nConversation history:\n{self.chat_history[-6:] if len(self.chat_history) > 6 else self.chat_history}\n\nCustomer's latest message: {user_input}\n\nDecide the next state:\n- If you need more information from the user to proceed, respond with only: 'AWAITING_INFO'.\n- If the problem is unresolved and needs escalation, respond with only: 'ESCALATION_PENDING'.\n- If the problem is resolved, respond with only: 'RESOLVED'.\n- If the user is off-topic, respond with only: 'OFF_TOPIC'.\n- Otherwise, respond with only: 'OPEN'.\n"""
                ).text.strip().upper()
                if state_check == 'AWAITING_INFO':
                    self.complaint_state = 'awaiting_info'
                    # Ask for more info (LLM-generated)
                    info_prompt = self.model.generate_content(
                        f"""Given this conversation, ask the user for any additional details needed to proceed with their complaint.\n\nConversation history:\n{self.chat_history[-6:] if len(self.chat_history) > 6 else self.chat_history}\n\nCustomer's latest message: {user_input}\n"""
                    ).text
                    self.chat_history.append({"role": "bot", "content": info_prompt})
                    return info_prompt
                elif state_check == 'ESCALATION_PENDING':
                    self.complaint_state = 'escalation_pending'
                    # Check for missing user info (all at once)
                    missing = []
                    if not self.user_info['name']:
                        missing.append('name')
                    if not self.user_info['mobile']:
                        missing.append('mobile number')
                    if not self.user_info['address']:
                        missing.append('address')
                    if missing:
                        return ("To log and escalate your complaint, please provide the following details in one message: "
                                + ', '.join(missing) + ". (e.g., 'My name is Rahul Sharma, my mobile number is 9876543210, my address is 123 Main Street, Kanpur')\n"
                                "Once I have this information, I will register your complaint, provide you with a complaint ID, and notify the concerned authority.")
                    # If all info present, register complaint and send email
                    self.current_complaint_id = self.db.add_complaint(user_input, "Complaint registered and escalated.")
                    self.send_complaint_email(
                        self.user_info['name'],
                        self.user_info['mobile'],
                        self.user_info['address'],
                        user_input,
                        self.current_complaint_id
                    )
                    response_text = (
                        f"Thank you for providing the details. Your complaint has been registered and escalated for further help.\n\n"
                        f"Complaint ID: {self.current_complaint_id}\n"
                        f"Name: {self.user_info['name']}\n"
                        f"Mobile: {self.user_info['mobile']}\n"
                        f"Address: {self.user_info['address']}\n"
                        f"Complaint: {user_input}\n"
                        "We have also informed the concerned authority at khushisaritaagrawal@gmail.com for further action. "
                        "You will be updated on the progress."
                    )
                    self.complaint_state = 'resolved'
                    self.chat_history.append({"role": "bot", "content": response_text})
                    return response_text
                elif state_check == 'RESOLVED':
                    self.complaint_state = 'resolved'
                    response_text = "Thank you for confirming. Your complaint has been marked as resolved. If you need further assistance, please let me know."
                    self.chat_history.append({"role": "bot", "content": response_text})
                    return response_text
                elif state_check == 'OFF_TOPIC':
                    self.complaint_state = 'idle'
                    response_text = "I'm a support assistant designed to help with real-world complaints, service issues, civic problems, and technical support. I can't assist with general knowledge questions or topics unrelated to real-world problems or services. Please let me know if you have any issues or concerns that need attention."
                    self.chat_history.append({"role": "bot", "content": response_text})
                    return response_text
                else:
                    self.complaint_state = 'open'
                    # Continue the conversation (LLM-generated)
                    continue_prompt = self.model.generate_content(
                        f"""Continue helping the user with their complaint based on the conversation so far.\n\nConversation history:\n{self.chat_history[-6:] if len(self.chat_history) > 6 else self.chat_history}\n\nCustomer's latest message: {user_input}\n"""
                    ).text
                    self.chat_history.append({"role": "bot", "content": continue_prompt})
                    return continue_prompt

            # Handle manual resolution
            if any(phrase in user_input.lower() for phrase in ["mark as resolved", "issue is resolved", "problem is fixed", "it's working now", "it works now", "complaint is resolved", "resolved"]):
                self.complaint_state = 'resolved'
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
            if not self.current_complaint_id or self.complaint_state == 'idle':
                # First, check if this is related to any real-world complaint or service issue
                relevance_check = self.model.generate_content(
                    f"""Analyze this customer message to determine if it describes a REAL-WORLD COMPLAINT, PROBLEM, or SERVICE ISSUE that should be handled by a support or civic assistant. This includes any report of something not working, broken, unsafe, missing, or needing attention, whether it's about products, services, infrastructure, public facilities, civic issues, or community problems.\n\nRELEVANT complaint topics:\n- Product or service complaints, issues, or problems\n- Account, billing, or payment issues\n- Technical support for products or services\n- How-to questions about products/services\n- Order, delivery, or shipping inquiries\n- Return, refund, or warranty requests\n- Service setup or configuration help\n- User account or login problems\n- Infrastructure or civic complaints (e.g., potholes, streetlights, sanitation, water, electricity, roads, public safety, garbage, pollution, noise, etc.)\n- Any report of a real-world problem that needs to be fixed or resolved\n\nNOT RELEVANT (reject these):\n- General knowledge questions (e.g., 'what is MCP server', 'explain blockchain')\n- Weather, news, entertainment, or unrelated topics\n- Technical definitions unrelated to any real-world service\n- Academic or educational queries\n- Personal advice or general life questions\n- Programming help unrelated to a real-world service\n- Random factual questions\n\nCustomer message: {user_input}\n\nRespond with only: 'RELEVANT' or 'NOT_RELEVANT'\n"""
                ).text.strip()
                
                # If not relevant to real-world complaints, politely redirect
                if "NOT_RELEVANT" in relevance_check.upper():
                    response_text = "I am a complaint resolution chatbot. I can only help you with registering and resolving real-world complaints. I cannot answer general questions, provide programming help, or assist with non-complaint related topics. Please let me know if you have any specific complaints that need to be registered."
                    self.chat_history.append({"role": "bot", "content": response_text})
                    return response_text
                
                # If relevant, then detect if it's a complaint
                complaint_detection = self.model.generate_content(
                    f"""Analyze this message and determine if it's a COMPLAINT (a report of a problem, issue, or something that needs to be fixed or resolved) or just a general inquiry.\n\nA COMPLAINT includes:\n- Product or service not working, broken, or defective\n- Service problems or poor experiences\n- Billing or payment issues\n- Delivery or shipping problems\n- Account or technical problems\n- Dissatisfaction with products/services\n- Infrastructure or civic issues (e.g., potholes, broken streetlights, sanitation, water, electricity, roads, public safety, garbage, pollution, noise, etc.)\n- Any report of a real-world problem that needs to be fixed or resolved\n\nNOT a complaint (general inquiry):\n- Questions about product or service features or how to use them\n- Information requests about services\n- How-to questions or usage instructions\n- General information requests\n- Casual greetings or thank you messages\n- General knowledge questions\n- Technical definitions\n- Academic or educational queries\n- Programming questions or code examples\n- Software development help\n- Algorithm or data structure questions\n- Any non-complaint related technical questions\n\nCustomer message: {user_input}\n\nRespond with only: 'COMPLAINT' or 'INQUIRY'\n"""
                ).text.strip()
                
                # Generate response with solutions
                initial_response = self.model.generate_content(
                    f"""You are a complaint resolution chatbot. Your ONLY purpose is to help users register and resolve their complaints. ALWAYS respond in the SAME language that the customer uses.

IMPORTANT: 
1. ONLY handle real-world complaints and service issues
2. Do NOT answer general knowledge questions, technical definitions, or off-topic queries
3. Do NOT provide general information or how-to guides
4. Do NOT provide programming help or code examples
5. Do NOT answer questions about software development
6. Focus ONLY on complaint registration and resolution

Your role is LIMITED to:
- Registering new complaints
- Collecting necessary information for complaint resolution
- Providing status updates on existing complaints
- Escalating complaints when needed
- Marking complaints as resolved

When helping customers:
1. FIRST: Determine if this is a legitimate complaint
2. If it's a complaint: Collect necessary details (name, contact, address)
3. If it's not a complaint: Politely redirect to complaint-related topics
4. Stay focused ONLY on complaint resolution

Customer's message: {user_input}

If this is a legitimate complaint, tell the user you will register it and provide a reference number for tracking. If it's not a complaint, politely redirect them to focus on their complaint and explain that you can only help with complaint registration and resolution.
"""
                ).text
                
                # Create complaint ID if this is a legitimate complaint
                if "COMPLAINT" in complaint_detection.upper():
                    self.complaint_state = 'open'
                    # Try to resolve the complaint first, do not ask for user info or send email yet
                    response_text = initial_response + "\n\nIf this does not resolve your issue or you need further help, please reply and I will escalate your complaint for further assistance."
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
                    - Provide specific solutions and troubleshooting steps for YOUR products ()
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