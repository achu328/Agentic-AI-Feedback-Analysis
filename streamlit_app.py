import streamlit as st
import pandas as pd
import yaml
import json
from datetime import datetime
import altair as alt

st.set_page_config(page_title="AI Feedback Processing Dashboard", layout="wide")

# -----------------------------------------------------
# Utility Functions
# -----------------------------------------------------
def safe_read_csv(path):
    try:
        return pd.read_csv(path)
    except:
        return pd.DataFrame()

def parse_json(val):
    try:
        return json.loads(val) if isinstance(val, str) else val
    except:
        return val

def save_config(config):
    with open("config.yaml", "w") as f:
        yaml.dump(config, f)
    st.success("Configuration saved!")

def save_tickets(df):
    df.to_csv("outputs/generated_tickets.csv", index=False)
    st.success("Ticket saved successfully!")

# -----------------------------------------------------
# Load Data
# -----------------------------------------------------
tickets = safe_read_csv("outputs/generated_tickets.csv")
logs = safe_read_csv("outputs/processing_log.csv")
metrics = safe_read_csv("outputs/metrics.csv")

# Load config
try:
    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)
except:
    config = {"classification_thresholds": {}, "default_priorities": {}}

# -----------------------------------------------------
# Sidebar Navigation
# -----------------------------------------------------
st.sidebar.title("Navigation")
page = st.sidebar.radio(
    "Go to", 
    ["Dashboard", "Configuration", "Manual Override", "Analytics"]
)

st.sidebar.markdown("### Outputs")
st.sidebar.write("📄 generated_tickets.csv")
st.sidebar.write("📄 processing_log.csv")
st.sidebar.write("📄 metrics.csv")


# =====================================================
# PAGE 1 — DASHBOARD
# =====================================================
if page == "Dashboard":
    st.title("📊 Feedback Processing Dashboard")

    if tickets.empty:
        st.warning("No tickets found. Run the processing pipeline first.")
        st.stop()

    # KPIs
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Tickets", len(tickets))
    col2.metric("Bug Reports", sum(tickets["category"] == "Bug"))
    col3.metric("Feature Requests", sum(tickets["category"] == "Feature Request"))
    col4.metric("Praise", sum(tickets["category"] == "Praise"))

    st.subheader("Recent Tickets")
    st.dataframe(tickets.tail(10), use_container_width=True)

    st.subheader("Category Distribution")
    st.bar_chart(tickets["category"].value_counts())

    st.subheader("Priority Distribution")
    st.bar_chart(tickets["priority"].value_counts())


# =====================================================
# PAGE 2 — CONFIGURATION
# =====================================================
elif page == "Configuration":
    st.title("⚙️ Configuration Settings")

    st.subheader("Classification Thresholds")
    for cat, val in config.get("classification_thresholds", {}).items():
        config["classification_thresholds"][cat] = st.slider(
            f"Threshold for {cat}", 0.0, 1.0, float(val), step=0.05
        )

    st.subheader("Default Priorities")
    for cat, pr in config.get("default_priorities", {}).items():
        config["default_priorities"][cat] = st.selectbox(
            f"Default Priority for {cat}",
            ["Critical", "High", "Medium", "Low"],
            index=["Critical", "High", "Medium", "Low"].index(pr)
        )

    if st.button("Save Config"):
        save_config(config)


# =====================================================
# PAGE 3 — MANUAL OVERRIDE
# =====================================================
elif page == "Manual Override":
    st.title("📝 Manual Ticket Override")

    if tickets.empty:
        st.warning("No tickets available for editing.")
        st.stop()

    ticket_ids = tickets["ticket_id"].tolist()
    selected_id = st.selectbox("Select Ticket", ticket_ids)

    ticket = tickets[tickets["ticket_id"] == selected_id].iloc[0]

    st.subheader("Edit Ticket")

    new_title = st.text_input("Title", ticket["title"])
    new_category = st.selectbox(
        "Category",
        ["Bug", "Feature Request", "Praise", "Complaint", "Spam"],
        index=["Bug", "Feature Request", "Praise", "Complaint", "Spam"].index(ticket["category"]),
    )
    new_priority = st.selectbox(
        "Priority",
        ["Critical", "High", "Medium", "Low"],
        index=["Critical", "High", "Medium", "Low"].index(ticket["priority"]),
    )

    new_details = st.text_area("Details (JSON)", ticket["details"], height=200)
    status = st.radio("Status", ["Pending", "Approved", "Needs Correction"])

    if st.button("Save"):
        idx = tickets[tickets["ticket_id"] == selected_id].index[0]

        tickets.at[idx, "title"] = new_title
        tickets.at[idx, "category"] = new_category
        tickets.at[idx, "priority"] = new_priority
        tickets.at[idx, "details"] = new_details
        tickets.at[idx, "status"] = status

        save_tickets(tickets)


# =====================================================
# PAGE 4 — ANALYTICS
# =====================================================
elif page == "Analytics":
    st.title("📈 Analytics & Metrics")

    if tickets.empty:
        st.warning("No ticket data found.")
        st.stop()

    st.subheader("Category Breakdown")
    chart1 = (
        alt.Chart(tickets)
        .mark_bar()
        .encode(x="category", y="count()")
    )
    st.altair_chart(chart1, use_container_width=True)

    st.subheader("Priority Breakdown")
    chart2 = (
        alt.Chart(tickets)
        .mark_arc()
        .encode(theta="count():Q", color="priority:N")
    )
    st.altair_chart(chart2, use_container_width=True)

    if not metrics.empty:
        st.subheader("Processing Metrics")
        st.dataframe(metrics, use_container_width=True)

    st.subheader("Processing Log")
    if logs.empty:
        st.info("No logs found.")
    else:
        st.dataframe(logs.tail(20), use_container_width=True)
