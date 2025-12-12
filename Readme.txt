 Capstone Project:Agentic AI Feedback Analysis & Ticket System using AutoGen


Project Overview"
This project is an Agentic AI System designed to automate the processing of customer feedback (App Store Reviews and Support Emails). 

Instead of simple keyword matching, it uses a Multi-Agent powered by AutoGen and GPT-4o-mini to intelligently classify feedback, extract technical details, and generate structured Jira-style tickets. It includes a Streamlit for human review and analytics.

Features:
Multi-Agent Architecture: Uses 5 specialized agents (Classifier, Bug Analyst, Feature Extractor, Ticket Creator, Quality Critic).
Intelligent Routing:Automatically detects if feedback is a Bug, Feature Request, Praise, or Complaint.
Technical Extraction:Extracts "Steps to Reproduce" for bugs and "User Impact" for feature requests.
Quality Control:A "Critic" agent reviews every ticket for accuracy before saving.
Interactive Dashboard:A Streamlit UI to view metrics, edit tickets, and analyze trends.

---

Project Structure
```text
├── data/
│   ├── app_store_reviews.csv    # Input Source 1 (Reviews)
│   └── support_emails.csv       # Input Source 2 (Emails)
├── outputs/
│   ├── generated_tickets.csv    # Final Output (The Tickets)
│   ├── processing_log.csv       # Log of agent actions
│   └── metrics.csv              # Performance metrics
├── main_app.py                  # CORE: The AutoGen Multi-Agent Backend
├── streamlit_app.py             # UI: The Analytics Dashboard
└── README.md                    # Project Documentation