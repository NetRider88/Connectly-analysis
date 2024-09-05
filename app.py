import streamlit as st
import pandas as pd
import plotly.express as px
from io import BytesIO


# Function to extract country name based on phone code
def get_country(phone_number):
    phone_number = str(phone_number)
    if phone_number.startswith("971"):
        return "UAE"
    elif phone_number.startswith("201"):
        return "Egypt"
    elif phone_number.startswith("973"):
        return "Bahrain"
    elif phone_number.startswith("964"):
        return "Iraq"
    elif phone_number.startswith("974"):
        return "Qatar"
    elif phone_number.startswith("965"):
        return "Kuwait"
    elif phone_number.startswith("968"):
        return "Oman"
    else:
        return "Other"

# Load CSV file
st.title("Connectly Campaign Analysis")
uploaded_file = st.file_uploader("Upload a CSV file", type="csv")

if uploaded_file:
    df = pd.read_csv(uploaded_file)

    # Check if required columns exist
    required_columns = {'customer_external_id', 'campaign_name', 'dispatched_at', 'sent_at', 'delivered_at', 'read_at', 'link_clicks'}
    if not required_columns.issubset(df.columns):
        st.error("CSV file does not contain required columns. Please check your file.")
    else:
        # Clean and process data
        df['customer_external_id'] = df['customer_external_id'].astype(str)
        df['Country'] = df['customer_external_id'].apply(get_country)

        # Convert date columns to datetime
        df['dispatched_at'] = pd.to_datetime(df['dispatched_at'], errors='coerce')
        df['sent_at'] = pd.to_datetime(df['sent_at'], errors='coerce')
        df['delivered_at'] = pd.to_datetime(df['delivered_at'], errors='coerce')
        df['read_at'] = pd.to_datetime(df['read_at'], errors='coerce')

        # Treat any non-empty value in 'link_clicks' as clicked
        df['Clicked'] = df['link_clicks'].notna() & (df['link_clicks'] != '')

        # Convert to period and then to string
        df['dispatched_month'] = df['dispatched_at'].dt.to_period('M').astype(str)
        df['sent_month'] = df['sent_at'].dt.to_period('M').astype(str)
        df['delivered_month'] = df['delivered_at'].dt.to_period('M').astype(str)
        df['read_month'] = df['read_at'].dt.to_period('M').astype(str)
        df['clicked_month'] = df['dispatched_at'].dt.to_period('M').astype(str)

        # Sidebar filters
        selected_countries = st.sidebar.multiselect("Select Country", df['Country'].unique(), default=df['Country'].unique())
        selected_months = st.sidebar.multiselect("Select Month", df['dispatched_month'].unique(), default=df['dispatched_month'].unique())
        selected_campaigns = st.sidebar.multiselect("Select Campaign", df['campaign_name'].unique(), default=df['campaign_name'].unique())

        filtered_df = df[
            (df['Country'].isin(selected_countries)) &
            (df['dispatched_month'].isin(selected_months)) &
            (df['campaign_name'].isin(selected_campaigns))
        ]

        # Group data by Country, Campaign, and Month
        grouped = filtered_df.groupby(['Country', 'campaign_name', 'dispatched_month']).agg(
            Dispatched=('dispatched_at', 'count'),
            Sent=('sent_at', 'count'),
            Read=('read_at', 'count'),
            Clicked=('Clicked', 'sum')
        ).reset_index()

        # Calculate month-on-month percentage changes
        grouped['Dispatched_MoM'] = grouped.groupby(['Country', 'campaign_name'])['Dispatched'].pct_change() * 100
        grouped['Sent_MoM'] = grouped.groupby(['Country', 'campaign_name'])['Sent'].pct_change() * 100
        grouped['Read_MoM'] = grouped.groupby(['Country', 'campaign_name'])['Read'].pct_change() * 100
        grouped['Clicked_MoM'] = grouped.groupby(['Country', 'campaign_name'])['Clicked'].pct_change() * 100

        # Fill NaN values with 0 for MoM percentages
        grouped.fillna(0, inplace=True)

        # Display data as a table
        st.subheader("Monthly Comparison per Country and Campaign")
        st.dataframe(grouped)

        # Visualize the data with bar charts for dispatched, sent, read, and clicked
        st.subheader("Visualizations")

        metrics = ["Dispatched", "Sent", "Read", "Clicked"]
        for metric in metrics:
            fig = px.bar(grouped, x='dispatched_month', y=metric, color='Country', barmode='group',
                         title=f"{metric} Messages by Month and Country")
            st.plotly_chart(fig)

        # Option to download the data as an Excel file
        st.subheader("Download Analysis")
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            grouped.to_excel(writer, index=False, sheet_name='Campaign Analysis')
            writer.close()
        st.download_button(label="Download as Excel", data=output.getvalue(), file_name="campaign_analysis.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
