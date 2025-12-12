import asyncio
import os
import json
import csv
import time
import pandas as pd
from pathlib import Path
from datetime import datetime

# AutoGen 0.4 Imports
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.conditions import TextMentionTermination
from autogen_ext.models.openai import OpenAIChatCompletionClient

# -------------------------------------------------------------------------
# CONFIGURATION
# -------------------------------------------------------------------------
DATA_DIR = Path("data")
OUTPUT_DIR = Path("outputs")
OUTPUT_DIR.mkdir(exist_ok=True)

# -------------------------------------------------------------------------
# MODEL SETUP (GPT-4o-mini)
# -------------------------------------------------------------------------
def get_model_client():
    return OpenAIChatCompletionClient(
        model="gpt-4o-mini",
        api_key="YOUR_OPENAI_API_KEY"  
    )

# -------------------------------------------------------------------------
# AGENT DEFINITIONS
# -------------------------------------------------------------------------
async def get_agent_team(model_client):
    # 1. Feedback Classifier
    classifier = AssistantAgent(
        name="Feedback_Classifier",
        model_client=model_client,
        system_message="""You are an expert Feedback Classifier.
        Your ONLY job is to categorize the input text into ONE of: 
        [Bug, Feature Request, Praise, Complaint, Spam].
        Also assign a Priority: [Critical, High, Medium, Low].
        Output strictly JSON: {"category": "...", "priority": "..."}"""
    )

    # 2. Bug Analyst
    bug_analyst = AssistantAgent(
        name="Bug_Analyst",
        model_client=model_client,
        system_message="""You are a QA Engineer. 
        IF the category is 'Bug':
        - Extract 'steps_to_reproduce' (list)
        - Identify 'device_info' (if present)
        - Estimate 'severity'
        IF NOT a Bug, return {"status": "skipped"}.
        Output strictly JSON."""
    )

    # 3. Feature Extractor
    feature_extractor = AssistantAgent(
        name="Feature_Extractor",
        model_client=model_client,
        system_message="""You are a Product Manager.
        IF the category is 'Feature Request':
        - Extract 'requested_feature' (concise description)
        - Estimate 'user_impact' (High/Med/Low)
        IF NOT a Feature Request, return {"status": "skipped"}.
        Output strictly JSON."""
    )

    # 4. Ticket Creator
    ticket_creator = AssistantAgent(
        name="Ticket_Creator",
        model_client=model_client,
        system_message="""You are a Jira Admin. 
        Compile the final ticket based on previous agent outputs.
        Schema:
        {
            "title": "Title",
            "category": "Category",
            "priority": "Priority",
            "details": { ...merge bug/feature details... },
            "reasoning": "Why this priority?"
        }
        Return ONLY valid JSON.
        """
    )

    # 5. Quality Critic
    quality_critic = AssistantAgent(
        name="Quality_Critic",
        model_client=model_client,
        system_message="""You are a Senior Reviewer.
        Check the Ticket Creator's output.
        - Is the title clear?
        - Is the priority reasonable?
        - Is the JSON valid?
        If GOOD, reply "APPROVED".
        If BAD, explain what to fix.
        """
    )

    return [classifier, bug_analyst, feature_extractor, ticket_creator, quality_critic]

# -------------------------------------------------------------------------
# PIPELINE LOGIC
# -------------------------------------------------------------------------
async def process_single_item(row_id, source_type, text):
    model_client = get_model_client()
    agents = await get_agent_team(model_client)
    
    # Termination: Stop when Critic says "APPROVED"
    termination = TextMentionTermination("APPROVED")

    # Round Robin Team
    team = RoundRobinGroupChat(
        participants=agents, 
        termination_condition=termination,
        max_turns=6
    )

    task_msg = f"""
    PROCESS THIS FEEDBACK (ID: {row_id}): "{text}"
    
    Pipeline:
    1. Classifier: Categorize.
    2. Bug_Analyst & Feature_Extractor: Extract details.
    3. Ticket_Creator: Draft JSON.
    4. Quality_Critic: Review.
    
    Ticket_Creator: Output final JSON before approval.
    """

    final_json = {}
    
    try:
        result_stream = team.run_stream(task=task_msg)
        async for message in result_stream:
            if hasattr(message, "content") and isinstance(message.content, str):
                # Attempt to grab the last valid JSON from the stream
                if "{" in message.content and "title" in message.content:
                    try:
                        start = message.content.find("{")
                        end = message.content.rfind("}") + 1
                        snippet = message.content[start:end]
                        data = json.loads(snippet)
                        if "title" in data:
                            final_json = data
                    except:
                        pass
    except Exception as e:
        print(f"⚠️ Error processing {row_id}: {e}")

    # Default if agents fail
    if not final_json:
        return {
            "title": f"Error Processing {row_id}",
            "category": "Error",
            "priority": "Low",
            "details": {"error": "Agents did not produce valid JSON"}
        }
        
    return final_json

# -------------------------------------------------------------------------
# MAIN EXECUTION
# -------------------------------------------------------------------------
async def main():
    print("🚀 Starting AutoGen Feedback System...")
    
    # 1. ROBUST DATA LOADING (Fixes Header Issues)
    try:
        reviews = pd.read_csv(DATA_DIR / "app_store_reviews.csv")
        emails = pd.read_csv(DATA_DIR / "support_emails.csv")
        
        # --- CRITICAL FIX: CLEAN COLUMN NAMES ---
        # This removes hidden spaces like " email_id" -> "email_id"
        reviews.columns = reviews.columns.str.strip()
        emails.columns = emails.columns.str.strip()
        # ----------------------------------------
        
        print(f"✅ Loaded {len(reviews)} reviews and {len(emails)} emails.")
        
    except Exception as e:
        print(f"❌ Error loading CSV files: {e}")
        print("Please check that 'app_store_reviews.csv' and 'support_emails.csv' are in the 'data/' folder.")
        return

    all_tickets = []
    
    # 2. PREPARE ITEMS
    # We process ALL items found in the CSVs
    items = []
    
    # Process Reviews
    if 'review_id' in reviews.columns and 'review_text' in reviews.columns:
        for _, r in reviews.iterrows():
            items.append({"id": str(r["review_id"]), "type": "Review", "text": str(r["review_text"])})
    else:
        print("⚠️ Warning: 'app_store_reviews.csv' missing 'review_id' or 'review_text' columns.")

    # Process Emails
    if 'email_id' in emails.columns and 'body' in emails.columns:
        for _, e in emails.iterrows():
            items.append({"id": str(e["email_id"]), "type": "Email", "text": str(e["body"])})
    else:
        print("⚠️ Warning: 'support_emails.csv' missing 'email_id' or 'body' columns.")

    print(f"📋 Processing {len(items)} total feedback items...")

    # 3. RUN AGENTS
    for i, item in enumerate(items):
        print(f"[{i+1}/{len(items)}] Processing {item['type']} {item['id']}...")
        result = await process_single_item(item['id'], item['type'], item['text'])
        
        ticket = {
            "ticket_id": f"TKT-{item['id']}",
            "title": result.get("title", "Untitled"),
            "category": result.get("category", "Uncategorized"),
            "priority": result.get("priority", "Low"),
            "details": json.dumps(result.get("details", {})),
            "source_id": item['id'],
            "source_type": item['type']
        }
        all_tickets.append(ticket)

    # 4. SAVE RESULTS
    df = pd.DataFrame(all_tickets)
    df.to_csv(OUTPUT_DIR / "generated_tickets.csv", index=False)
    
    # Save Metrics
    metrics = [{"metric": "total_tickets", "value": len(all_tickets)}]
    pd.DataFrame(metrics).to_csv(OUTPUT_DIR / "metrics.csv", index=False)
    
    # Create log file
    pd.DataFrame(columns=["timestamp", "action"]).to_csv(OUTPUT_DIR / "processing_log.csv", index=False)

    print(f"\n🎉 Success! Processed {len(all_tickets)} tickets.")
    print(f"📂 Output saved to: {OUTPUT_DIR}/generated_tickets.csv")

if __name__ == "__main__":
    asyncio.run(main())