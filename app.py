import streamlit as st
import pandas as pd
import plotly.express as px
from io import BytesIO
import phonenumbers
from phonenumbers.phonenumberutil import region_code_for_number
import pycountry

# Function to extract country based on phone number using phonenumbers library
def get_country(phone_number):
    phone_number = str(phone_number)
    try:
        parsed_number = phonenumbers.parse("+" + phone_number, None)
        country_code = region_code_for_number(parsed_number)
        country = pycountry.countries.get(alpha_2=country_code)
        return country.name if country else "Unknown"
    except phonenumbers.NumberParseException:
        return "Invalid"

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

        # Convert date columns to datetime (handle potential errors)
        for col in ['dispatched_at', 'sent_at', 'delivered_at', 'read_at']:
            try:
                df[col] = pd.to_datetime(df[col], errors='coerce')
            except:
                pass

        # Treat any non-empty value in 'link_clicks' as clicked
        df['Clicked'] = df['link_clicks'].notna() & (df['link_clicks'] != '')

        # Create read_day and read_hour columns (if not already created)
        if 'read_at' in df.columns:
            if pd.__version__ >= '1.1.0':
                df['read_at'] = pd.to_datetime(df['read_at'], errors='coerce')
            else:
                try:
                    df['read_at'] = pd.to_datetime(df['read_at'])
                except:
                    pass
            df['read_day'] = df['read_at'].dt.day_name()
            df['read_hour'] = df['read_at'].dt.hour

        # Convert to period and then to string
        df['dispatched_month'] = df['dispatched_at'].dt.to_period('M').astype(str)
        df['sent_month'] = df['sent_at'].dt.to_period('M').astype(str)
        df['delivered_month'] = df['delivered_at'].dt.to_period('M').astype(str)
        df['read_month'] = df['read_at'].dt.to_period('M').astype(str)
        df['clicked_month'] = df['dispatched_at'].dt.to_period('M').astype(str)

        # Sidebar filters
        preset_countries = ['Egypt', 'Kuwait', 'United Arab Emirates', 'Iraq', 'Bahrain', 'Jordan', 'Oman', 'Qatar']
        selected_countries = st.sidebar.multiselect("Select Country", df['Country'].unique(), default=preset_countries)
        selected_months = st.sidebar.multiselect("Select Month", df['dispatched_month'].unique(), default=df['dispatched_month'].unique())
        selected_campaigns = st.sidebar.multiselect("Select Campaign", df['campaign_name'].unique(), default=df['campaign_name'].unique())

        filtered_df = df[
            (df['Country'].isin(selected_countries)) &
            (df['dispatched_month'].isin(selected_months)) &
            (df['campaign_name'].isin(selected_campaigns))
        ]

        # Group data by Country
        funnel_data = filtered_df.groupby('Country').agg(
            Dispatched=('dispatched_at', 'count'),
            Sent=('sent_at', 'count'),
            Delivered=('delivered_at', lambda x: x.notna().sum()),  # Count non-null entries in 'delivered_at'
            Read=('read_at', 'count'),
            Clicked=('Clicked', 'sum')
        ).reset_index()

        # Prepare data for funnel chart
        funnel_df = funnel_data.melt(id_vars='Country', value_vars=['Dispatched', 'Sent', 'Delivered', 'Read', 'Clicked'],
                                     var_name='Stage', value_name='Count')

        # Plot funnel chart
        st.subheader("Campaign Funnel Analysis per Country")
        fig_funnel = px.bar(funnel_df, x='Country', y='Count', color='Stage',
                            color_discrete_map={
                                'Dispatched': 'gray',
                                'Sent': 'blue',
                                'Delivered': 'green',
                                'Read': 'orange',
                                'Clicked': 'red'
                            },
                            title='Campaign Funnel Analysis per Country',
                            labels={'Count': 'Number of Messages'})
        fig_funnel.update_layout(title_font_size=20, xaxis_title='Country', yaxis_title='Number of Messages')
        fig_funnel.update_xaxes(tickangle=45)
        st.plotly_chart(fig_funnel)

        # Other visualizations and downloads
        st.subheader("Visualizations")

        metrics = ["Dispatched", "Sent", "Read", "Clicked"]
        for metric in metrics:
            fig = px.bar(funnel_data, x='Country', y=metric, color='Country', barmode='group',
                         title=f"{metric} Messages by Country",
                         labels={'Country': 'Country', metric: f'{metric} Count'})
            fig.update_layout(title_font_size=20, xaxis_title='Country', yaxis_title=f'{metric} Count')
            st.plotly_chart(fig)

        st.subheader("Most Common Day and Hour for 'Read'")

        # Check if 'read_day' and 'read_hour' exist before grouping
        if 'read_day' in filtered_df.columns and 'read_hour' in filtered_df.columns:
            read_day_group = filtered_df.groupby('read_day')['read_at'].count().reset_index().sort_values('read_at', ascending=False)
            read_hour_group = filtered_df.groupby('read_hour')['read_at'].count().reset_index().sort_values('read_hour')

            # Plot most common day for 'read_at'
            fig_day = px.bar(read_day_group, x='read_day', y='read_at', title="Most Common Day for 'Read'")
            st.plotly_chart(fig_day)

            # Plot most common hour for 'read_at'
            fig_hour = px.bar(read_hour_group, x='read_hour', y='read_at', title="Most Common Hour for 'Read'")
            st.plotly_chart(fig_hour)
        else:
            st.error("Columns 'read_day' or 'read_hour' are missing in the filtered DataFrame.")


 # Create a heatmap for number of messages delivered per country
        st.subheader("Messages Delivered Heatmap")
        country_delivered = filtered_df.groupby('Country')['delivered_at'].count().reset_index()
        country_delivered = country_delivered.rename(columns={'delivered_at': 'Delivered'})

        fig_map = px.choropleth(
            country_delivered,
            locations='Country',
            locationmode='country names',
            color='Delivered',
            color_continuous_scale='RdBu',
            title='Number of Messages Delivered per Country'
        )
        fig_map.update_geos(showcoastlines=True, coastlinecolor="Black", showland=True, landcolor="lightgray")
        fig_map.update_layout(title_font_size=20)
        st.plotly_chart(fig_map)

        
        # Download button for cleaned DataFrame
        def convert_df(df):
            return df.to_csv(index=False).encode('utf-8')

        st.download_button(
            label="Download Cleaned Data",
            data=convert_df(df),
            file_name='cleaned_data.csv',
            mime='text/csv'
        )
