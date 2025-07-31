import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
from datetime import datetime, timedelta
import time
from main import run_marketing_agent, MarketingState
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Page configuration
st.set_page_config(
    page_title="Marketing Analytics Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f77b4;
    }
    .success-message {
        background-color: #d4edda;
        color: #155724;
        padding: 1rem;
        border-radius: 0.5rem;
        border: 1px solid #c3e6cb;
    }
    .error-message {
        background-color: #f8d7da;
        color: #721c24;
        padding: 1rem;
        border-radius: 0.5rem;
        border: 1px solid #f5c6cb;
    }
</style>
""", unsafe_allow_html=True)

def create_lead_source_chart(classified_data):
    """Create a pie chart for lead sources"""
    if not classified_data:
        return None
    
    sources = list(classified_data.keys())
    counts = [len(leads) for leads in classified_data.values()]
    
    fig = px.pie(
        values=counts,
        names=sources,
        title="Lead Distribution by Source",
        color_discrete_sequence=px.colors.qualitative.Set3
    )
    fig.update_traces(textposition='inside', textinfo='percent+label')
    return fig

def create_status_chart(classified_data):
    """Create a bar chart for lead statuses"""
    if not classified_data:
        return None
    
    status_data = []
    for source, leads in classified_data.items():
        status_counts = {}
        for lead in leads:
            status = lead.get("Lead_Status", "Unknown")
            status_counts[status] = status_counts.get(status, 0) + 1
        
        for status, count in status_counts.items():
            status_data.append({
                "Lead Source": source,
                "Status": status,
                "Count": count
            })
    
    if not status_data:
        return None
    
    df = pd.DataFrame(status_data)
    fig = px.bar(
        df,
        x="Lead Source",
        y="Count",
        color="Status",
        title="Lead Status by Source",
        barmode="group"
    )
    return fig

def create_disposition_chart(classified_data):
    """Create a bar chart for lead dispositions"""
    if not classified_data:
        return None
    
    disposition_data = []
    for source, leads in classified_data.items():
        disposition_counts = {}
        for lead in leads:
            disposition = lead.get("Disposition", "Unknown")
            disposition_counts[disposition] = disposition_counts.get(disposition, 0) + 1
        
        for disposition, count in disposition_counts.items():
            disposition_data.append({
                "Lead Source": source,
                "Disposition": disposition,
                "Count": count
            })
    
    if not disposition_data:
        return None
    
    df = pd.DataFrame(disposition_data)
    fig = px.bar(
        df,
        x="Lead Source",
        y="Count",
        color="Disposition",
        title="Lead Disposition by Source",
        barmode="group"
    )
    return fig

def create_campaign_analysis(classified_data):
    """Create campaign analysis charts"""
    if not classified_data:
        return None, None
    
    # Campaign data
    campaign_data = []
    adset_data = []
    
    for source, leads in classified_data.items():
        campaigns = {}
        adsets = {}
        
        for lead in leads:
            campaign = lead.get("Campaign", "Unknown")
            adset = lead.get("Adset_Name", "Unknown")
            
            campaigns[campaign] = campaigns.get(campaign, 0) + 1
            adsets[adset] = adsets.get(adset, 0) + 1
        
        for campaign, count in campaigns.items():
            campaign_data.append({
                "Lead Source": source,
                "Campaign": campaign,
                "Count": count
            })
        
        for adset, count in adsets.items():
            adset_data.append({
                "Lead Source": source,
                "Ad Set": adset,
                "Count": count
            })
    
    campaign_df = pd.DataFrame(campaign_data)
    adset_df = pd.DataFrame(adset_data)
    
    campaign_fig = px.bar(
        campaign_df,
        x="Campaign",
        y="Count",
        color="Lead Source",
        title="Campaign Performance",
        barmode="group"
    )
    campaign_fig.update_xaxes(tickangle=45)
    
    adset_fig = px.bar(
        adset_df,
        x="Ad Set",
        y="Count",
        color="Lead Source",
        title="Ad Set Performance",
        barmode="group"
    )
    adset_fig.update_xaxes(tickangle=45)
    
    return campaign_fig, adset_fig

def display_metrics(classified_data):
    """Display key metrics"""
    if not classified_data:
        return
    
    col1, col2, col3, col4 = st.columns(4)
    
    total_leads = sum(len(leads) for leads in classified_data.values())
    total_sources = len(classified_data)
    
    # Calculate conversion rate (leads with status other than null/unknown)
    qualified_leads = 0
    for leads in classified_data.values():
        for lead in leads:
            status = lead.get("Lead_Status")
            if status and status not in ["null", "Unknown", None]:
                qualified_leads += 1
    
    conversion_rate = (qualified_leads / total_leads * 100) if total_leads > 0 else 0
    
    with col1:
        st.metric("Total Leads", total_leads)
    
    with col2:
        st.metric("Lead Sources", total_sources)
    
    with col3:
        st.metric("Qualified Leads", qualified_leads)
    
    with col4:
        st.metric("Conversion Rate", f"{conversion_rate:.1f}%")

def main():
    st.markdown('<h1 class="main-header">📊 Marketing Analytics Dashboard</h1>', unsafe_allow_html=True)
    
    # Sidebar
    st.sidebar.title("🎛️ Controls")
    
    # Date range selector
    st.sidebar.subheader("📅 Date Range")
    date_option = st.sidebar.selectbox(
        "Select date range:",
        ["Last 24 hours", "Last 7 days", "Last 30 days", "Custom range"]
    )
    
    if date_option == "Custom range":
        start_date = st.sidebar.date_input("Start date", datetime.now() - timedelta(days=7))
        end_date = st.sidebar.date_input("End date", datetime.now())
    
    # Run analysis button
    st.sidebar.subheader("🚀 Analysis")
    run_analysis = st.sidebar.button("Run Marketing Analysis", type="primary")
    
    # Initialize session state
    if 'analysis_result' not in st.session_state:
        st.session_state.analysis_result = None
    if 'analysis_time' not in st.session_state:
        st.session_state.analysis_time = None
    
    # Main content area
    if run_analysis:
        with st.spinner("🔄 Running marketing analysis..."):
            try:
                start_time = time.time()
                result = run_marketing_agent()
                end_time = time.time()
                
                st.session_state.analysis_result = result
                st.session_state.analysis_time = end_time - start_time
                
                st.success("✅ Analysis completed successfully!")
                
            except Exception as e:
                st.error(f"❌ Analysis failed: {str(e)}")
                logger.error(f"Analysis failed: {e}")
    
    # Display results if available
    if st.session_state.analysis_result:
        result = st.session_state.analysis_result
        
        # Show execution time
        if st.session_state.analysis_time:
            st.info(f"⏱️ Analysis completed in {st.session_state.analysis_time:.2f} seconds")
        
        # Check for errors
        if result.get("error"):
            st.error(f"❌ Error: {result['error']}")
            return
        
        # Display metrics
        st.subheader("📈 Key Metrics")
        display_metrics(result.get("classified_data", {}))
        
        # Create tabs for different views
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "📊 Overview", 
            "📈 Charts", 
            "🎯 Campaign Analysis", 
            "📋 Raw Data", 
            "💡 AI Insights"
        ])
        
        with tab1:
            st.subheader("📊 Data Overview")
            
            # Summary statistics
            classified_data = result.get("classified_data", {})
            if classified_data:
                summary_data = []
                for source, leads in classified_data.items():
                    status_counts = {}
                    disposition_counts = {}
                    
                    for lead in leads:
                        status = lead.get("Lead_Status", "Unknown")
                        disposition = lead.get("Disposition", "Unknown")
                        
                        status_counts[status] = status_counts.get(status, 0) + 1
                        disposition_counts[disposition] = disposition_counts.get(disposition, 0) + 1
                    
                    summary_data.append({
                        "Lead Source": source,
                        "Total Leads": len(leads),
                        "Most Common Status": max(status_counts.items(), key=lambda x: x[1])[0] if status_counts else "N/A",
                        "Most Common Disposition": max(disposition_counts.items(), key=lambda x: x[1])[0] if disposition_counts else "N/A"
                    })
                
                summary_df = pd.DataFrame(summary_data)
                st.dataframe(summary_df, use_container_width=True)
        
        with tab2:
            st.subheader("📈 Data Visualizations")
            
            classified_data = result.get("classified_data", {})
            if classified_data:
                # Lead source distribution
                lead_source_fig = create_lead_source_chart(classified_data)
                if lead_source_fig:
                    st.plotly_chart(lead_source_fig, use_container_width=True)
                
                # Lead status chart
                status_fig = create_status_chart(classified_data)
                if status_fig:
                    st.plotly_chart(status_fig, use_container_width=True)
                
                # Lead disposition chart
                disposition_fig = create_disposition_chart(classified_data)
                if disposition_fig:
                    st.plotly_chart(disposition_fig, use_container_width=True)
            else:
                st.warning("No data available for visualization")
        
        with tab3:
            st.subheader("🎯 Campaign Analysis")
            
            classified_data = result.get("classified_data", {})
            if classified_data:
                campaign_fig, adset_fig = create_campaign_analysis(classified_data)
                
                if campaign_fig:
                    st.plotly_chart(campaign_fig, use_container_width=True)
                
                if adset_fig:
                    st.plotly_chart(adset_fig, use_container_width=True)
                
                # Campaign summary table
                st.subheader("📋 Campaign Summary")
                campaign_summary = []
                for source, leads in classified_data.items():
                    campaigns = {}
                    for lead in leads:
                        campaign = lead.get("Campaign", "Unknown")
                        campaigns[campaign] = campaigns.get(campaign, 0) + 1
                    
                    for campaign, count in campaigns.items():
                        campaign_summary.append({
                            "Lead Source": source,
                            "Campaign": campaign,
                            "Lead Count": count
                        })
                
                if campaign_summary:
                    campaign_df = pd.DataFrame(campaign_summary)
                    st.dataframe(campaign_df, use_container_width=True)
            else:
                st.warning("No campaign data available")
        
        with tab4:
            st.subheader("📋 Raw Data")
            
            raw_data = result.get("raw_data", {})
            if raw_data and "data" in raw_data:
                df = pd.DataFrame(raw_data["data"])
                st.dataframe(df, use_container_width=True)
                
                # Download button
                csv = df.to_csv(index=False)
                st.download_button(
                    label="📥 Download CSV",
                    data=csv,
                    file_name=f"marketing_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
            else:
                st.warning("No raw data available")
        
        with tab5:
            st.subheader("💡 AI-Generated Insights")
            
            insights = result.get("insights", "")
            if insights:
                st.markdown(insights)
                
                # Download insights
                st.download_button(
                    label="📥 Download Insights Report",
                    data=insights,
                    file_name=f"marketing_insights_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
                    mime="text/markdown"
                )
            else:
                st.warning("No insights available")
    
    else:
        # Welcome message when no analysis has been run
        st.markdown("""
        ## 🎯 Welcome to the Marketing Analytics Dashboard
        
        This dashboard helps you analyze your marketing data and generate insights using AI.
        
        ### 🚀 Getting Started:
        1. **Configure Settings**: Use the sidebar to set your preferred date range
        2. **Run Analysis**: Click the "Run Marketing Analysis" button to start
        3. **Explore Results**: View charts, metrics, and AI-generated insights
        
        ### 📊 What You'll Get:
        - **Key Metrics**: Total leads, conversion rates, and performance indicators
        - **Data Visualizations**: Charts showing lead distribution and trends
        - **Campaign Analysis**: Performance breakdown by campaigns and ad sets
        - **Raw Data**: Complete dataset for further analysis
        - **AI Insights**: Intelligent recommendations and observations
        
        ### ⚙️ Features:
        - Real-time data fetching from Zoho CRM
        - AI-powered insights generation
        - Interactive charts and visualizations
        - Export capabilities for reports and data
        """)
        
        # Quick stats placeholder
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Ready to Analyze", "✅", "Click 'Run Analysis' to start")
        with col2:
            st.metric("Data Sources", "Zoho CRM", "Connected and ready")
        with col3:
            st.metric("AI Model", "GPT-4o-mini", "Powered by OpenAI")

if __name__ == "__main__":
    main() 