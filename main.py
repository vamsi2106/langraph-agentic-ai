import requests
import json
from langgraph.graph import StateGraph, END
from typing import Dict, List, TypedDict, Optional
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
import os
from datetime import datetime, timedelta
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables (use .env file or set in your environment)
# DO NOT hardcode API keys in source code
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ZOHO_CLIENT_ID = os.getenv("ZOHO_CLIENT_ID")
ZOHO_CLIENT_SECRET = os.getenv("ZOHO_CLIENT_SECRET")
ZOHO_REFRESH_TOKEN = os.getenv("ZOHO_REFRESH_TOKEN")

# Validate required environment variables
if not all([OPENAI_API_KEY, ZOHO_CLIENT_ID, ZOHO_CLIENT_SECRET, ZOHO_REFRESH_TOKEN]):
    raise ValueError("Missing required environment variables. Please set OPENAI_API_KEY, ZOHO_CLIENT_ID, ZOHO_CLIENT_SECRET, and ZOHO_REFRESH_TOKEN")

# Initialize LLM
llm = ChatOpenAI(
    model="gpt-4o-mini",  # Using a more cost-effective model
    temperature=0.1,
    api_key=OPENAI_API_KEY
)

# Define state to track data through the workflow
class MarketingState(TypedDict):
    access_token: Optional[str]
    raw_data: Dict
    classified_data: Dict[str, List[Dict]]
    insights: str
    error: Optional[str]

# Agent 1: Token Refresher
def refresh_token(state: MarketingState) -> MarketingState:
    try:
        logger.info("Refreshing Zoho access token...")
        url = "https://accounts.zoho.com/oauth/v2/token"
        headers = {
            "Cookie": "iamcsr=86c1247a-dbaa-4de5-a2bd-32cabf541dd7; _zcsr_tmp=86c1247a-dbaa-4de5-a2bd-32cabf541dd7; zalb_b266a5bf57=9f371135a524e2d1f51eb9f41fa26c60"
        }
        data = {
            "client_id": ZOHO_CLIENT_ID,
            "client_secret": ZOHO_CLIENT_SECRET,
            "refresh_token": ZOHO_REFRESH_TOKEN,
            "grant_type": "refresh_token"
        }
        response = requests.post(url, headers=headers, data=data)
        response.raise_for_status()
        token_data = response.json()
        state["access_token"] = token_data.get("access_token")
        state["error"] = None if state["access_token"] else "No access token received"
        logger.info("Token refresh successful")
    except Exception as e:
        state["error"] = f"Token refresh failed: {str(e)}"
        state["access_token"] = None
        logger.error(f"Token refresh failed: {e}")
    return state

# Agent 2: Data Fetcher
def fetch_data(state: MarketingState) -> MarketingState:
    if state.get("error") or not state.get("access_token"):
        state["error"] = state.get("error") or "No valid access token"
        state["raw_data"] = {}
        return state
    try:
        logger.info("Fetching data from Zoho CRM...")
        url = "https://www.zohoapis.com/crm/v8/coql"
        headers = {
            "Authorization": f"Bearer {state['access_token']}",
            "Content-Type": "application/json",
            "Cookie": "crmcsr=ede8174b-58c8-4987-8734-ab308fb171c2; _zcsr_tmp=ede8174b-58c8-4987-8734-ab308fb171c2"
        }
        # Calculate date range for the query (yesterday to today)
        today = datetime.now().strftime("%Y-%m-%dT23:59:59+05:30")
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%dT00:00:00+05:30")
        payload = {
            "select_query": f"SELECT Full_Name, Phone, Product, Lead_Source, subsource, Lead_Status, Disposition, Agency, Ad_Name, Adset_Name, Campaign, utm_campaign FROM Contacts WHERE Created_Time >= '{yesterday}' AND Created_Time <= '{today}'"
        }
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        state["raw_data"] = response.json()
        state["error"] = None
        logger.info(f"Successfully fetched {len(state['raw_data'].get('data', []))} records")
    except Exception as e:
        state["error"] = f"Data fetch failed: {str(e)}"
        state["raw_data"] = {}
        logger.error(f"Data fetch failed: {e}")
    return state

# Agent 3: Data Classifier
def classify_data(state: MarketingState) -> MarketingState:
    if state.get("error"):
        return state
    logger.info("Classifying data by lead source...")
    raw_data = state["raw_data"].get("data", [])
    classified = {}
    for lead in raw_data:
        lead_source = lead.get("Lead_Source", "Unknown")
        if lead_source not in classified:
            classified[lead_source] = []
        classified[lead_source].append(lead)
    state["classified_data"] = classified
    logger.info(f"Data classified into {len(classified)} lead sources")
    return state

# Agent 4: Insights Generator
def generate_insights(state: MarketingState) -> MarketingState:
    if state.get("error"):
        return state
    logger.info("Generating insights using LLM...")
    classified_data = state["classified_data"]
    
    # Prepare prompt for LLM
    prompt_template = PromptTemplate(
        input_variables=["classified_data"],
        template="""You are a marketing strategist analyzing lead data from a CRM system. The data is classified by Lead_Source as follows:

{classified_data}

Provide detailed insights for the marketing head and strategists, focusing on:
1. Lead volume and quality (based on Lead_Status and Disposition) by Lead_Source.
2. Effectiveness of different campaigns and ad sets (use Agency, Ad_Name, Adset_Name, Campaign, utm_campaign).
3. Recommendations for optimizing marketing strategies, including which Lead_Sources to prioritize or adjust.

Return a concise report in markdown format."""
    )
    # Format classified data for prompt
    classified_summary = {}
    for source, leads in classified_data.items():
        classified_summary[source] = {
            "count": len(leads),
            "status_counts": {},
            "disposition_counts": {},
            "campaigns": set(),
            "adsets": set(),
            "agencies": set(),
            "products": set()
        }
        for lead in leads:
            status = lead.get("Lead_Status", "None")
            disposition = lead.get("Disposition", "None")
            classified_summary[source]["status_counts"][status] = classified_summary[source]["status_counts"].get(status, 0) + 1
            classified_summary[source]["disposition_counts"][disposition] = classified_summary[source]["disposition_counts"].get(disposition, 0) + 1
            if lead.get("Campaign"):
                classified_summary[source]["campaigns"].add(lead["Campaign"])
            if lead.get("Adset_Name"):
                classified_summary[source]["adsets"].add(lead["Adset_Name"])
            if lead.get("Agency"):
                classified_summary[source]["agencies"].add(lead["Agency"])
            if lead.get("Product"):
                classified_summary[source]["products"].add(lead["Product"])
    
    # Convert sets to lists for JSON serialization
    for source in classified_summary:
        classified_summary[source]["campaigns"] = list(classified_summary[source]["campaigns"])
        classified_summary[source]["adsets"] = list(classified_summary[source]["adsets"])
        classified_summary[source]["agencies"] = list(classified_summary[source]["agencies"])
        classified_summary[source]["products"] = list(classified_summary[source]["products"])
    
    # Generate insights using LLM
    insights = llm.invoke(prompt_template.format(classified_data=json.dumps(classified_summary, indent=2)))
    state["insights"] = insights.content
    logger.info("Insights generation completed")
    return state

# Define the workflow
workflow = StateGraph(MarketingState)

# Add nodes
workflow.add_node("refresh_token", refresh_token)
workflow.add_node("fetch_data", fetch_data)
workflow.add_node("classify_data", classify_data)
workflow.add_node("generate_insights", generate_insights)

# Define edges
workflow.add_edge("refresh_token", "fetch_data")
workflow.add_edge("fetch_data", "classify_data")
workflow.add_edge("classify_data", "generate_insights")
workflow.add_edge("generate_insights", END)

# Set entry point
workflow.set_entry_point("refresh_token")

# Compile the graph
graph = workflow.compile()

# Execute the workflow
def run_marketing_agent() -> MarketingState:
    initial_state = MarketingState(
        access_token=None,
        raw_data={},
        classified_data={},
        insights="",
        error=None
    )
    result = graph.invoke(initial_state)
    return result

# Run the agent and output insights
if __name__ == "__main__":
    try:
        result = run_marketing_agent()
        if result["error"]:
            print(f"Error: {result['error']}")
        else:
            print(result["insights"])
    except Exception as e:
        logger.error(f"Workflow execution failed: {e}")
        print(f"Workflow execution failed: {e}")