from datetime import datetime
from urllib.error import URLError
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import requests
import json

@st.cache
def state_options():
    '''
    Return the state names of all available states in India.
    Fucntion cached because this is a consistent data.

    Returns
    -------
    state_names : List
        All state names on India fetched and stored earlier in a local file.
        Names fetched from government server.
    '''
    
    path = '.././Data/State_Names.csv'
    df = pd.read_csv(path)
    state_names = df['state_name'].unique().tolist()
    return state_names

@st.cache
def district_options(state_name):
    '''
    Returns the names of all districts in a particular state.
    Fucntion cached because this is a consistent data.

    Parameters
    ----------
    state_name : string
        The statename for which all districts are required

    Returns
    -------
    district_names : List
        List of all districts in the given state
    '''
    
    path = '.././Data/State_And_Disctrict_Names.csv'
    df = pd.read_csv(path)
    df = df[df['state_name']==state_name]
    district_names = df['district_name'].unique().tolist()
    return district_names

def get_Vax_Data(state, district, age):
    '''
    This is the main function of the app.
    It connects to the server to scrape data for vaccine availability based on selected district,
    state and age.

    Parameters
    ----------
    state : string
        Name of state for which data is required.
    district : string
        Name of district for which data is required.
    age : int
        Age for checking eligibility

    Returns
    -------
    vax_info_all_sessions_df : Dataframe
        Dataframe table containing all required vaccine info.
    pincode_list : List
        List of all unique pincodes in a given district.
    '''
    
    path = '.././Data/State_And_Disctrict_Names.csv'
    df = pd.read_csv(path)
    DIST_ID = df[(df['district_name'] == district) & (df['state_name'] == state)]['district_id'].values[0]
    START_DATE = datetime.today().strftime('%d-%m-%Y')
    VAX_DATA_PORTAL = f'https://cdn-api.co-vin.in/api/v2/appointment/sessions/public/calendarByDistrict?district_id={DIST_ID}&date={START_DATE}'
    res = requests.get(VAX_DATA_PORTAL)
    vax_info_df = pd.DataFrame(json.loads(res.text)['centers'])
    vax_info_df["from"] = pd.to_datetime(vax_info_df["from"]).dt.strftime('%H:%M')
    vax_info_df["to"] = pd.to_datetime(vax_info_df["to"]).dt.strftime('%H:%M')
    vax_info_df["Timing"] = vax_info_df["from"] + " - " + vax_info_df["to"]
    pincode_list = vax_info_df['pincode'].unique().tolist()
    
    vax_info_all_sessions_df = vax_info_df.explode('sessions').reset_index(drop=True)
    
    vax_info_all_sessions_df['Min_Age'] = vax_info_all_sessions_df.sessions.apply(lambda x: x['min_age_limit'])
    vax_info_all_sessions_df['Doses_Available'] = vax_info_all_sessions_df.sessions.apply(lambda x: x['available_capacity'])
    vax_info_all_sessions_df['Vaccine'] = vax_info_all_sessions_df.sessions.apply(lambda x: x['vaccine']).fillna('UNKNOWN')
    # vax_info_all_sessions_df['Date'] =  pd.to_datetime(vax_info_all_sessions_df.sessions.apply(lambda x: x['date'])).dt.strftime('%d-%m-%Y')
    vax_info_all_sessions_df['Date'] =  vax_info_all_sessions_df.sessions.apply(lambda x: x['date'])
    
    vax_info_all_sessions_df = vax_info_all_sessions_df[vax_info_all_sessions_df['Min_Age'] == age]
    return vax_info_all_sessions_df, pincode_list


st.set_page_config(page_title='Vaccine Slot Tracker' , page_icon=":syringe:",layout='wide', initial_sidebar_state='auto')
st.title('CoWin : Vaccine Availability :syringe:')

state = st.sidebar.selectbox("Choose Your State", state_options())
district = st.sidebar.selectbox("Choose Your District", district_options(state))
age = st.sidebar.slider("Choose Your Age", min_value=0, max_value=100, step=1, value=45)
if age < 18:
    age=0
elif (age>=18) and (age<45):
    age=18
elif age > 45:
    age=45

progress_bar = st.progress(0)
progress_message = st.empty()

try:
    progress_message.text('Fetching data. Please wait...')
    progress_bar.progress(10)
    vax_df, pincode_list = get_Vax_Data(state, district, age)
    progress_bar.progress(100)
    
    # Filter Based on PINCODE
    pincode = None
    search_by_pin = st.sidebar.checkbox('Filter by Pincode')
    if search_by_pin:
        selected_pincode = st.sidebar.selectbox("Select Pincode",options=sorted(set(pincode_list)))
        vax_df = vax_df[vax_df["pincode"] == selected_pincode]
    
    #Filter Based on Availability
    only_available = st.sidebar.checkbox('Show only Available')
    if only_available:
        vax_df = vax_df[vax_df["Doses_Available"] > 0]
    
    # Only Selecting Important Columns
    cols_to_show = ['name', 'state_name', 'district_name', 'pincode', 'from', 'to', 'fee_type', 'Min_Age', 'Doses_Available',
                    'Vaccine', 'Date']
    vax_df = vax_df[cols_to_show]
    plot_df = vax_df.groupby(['Date']).sum()['Doses_Available'].reset_index()
    fig = go.Figure([go.Bar(x=plot_df['Date'], y=plot_df['Doses_Available'])])
    
    vax_df.rename(columns={'name':'Name', 'state_name':'State', 'district_name':'District', 'pincode':'Pincode', 'from':'From',
                           'to': 'To', 'fee_type': 'Free/Paid', 'Min_Age':'Min Age', 'Doses_Available':'Available Doses',
                           'Vaccine':'Vaccine', 'Date':'Date'}, inplace=True)
    
    st.markdown(f'## Availability in {district} ({state})')
    st.plotly_chart(fig, use_container_width=True)
    st.markdown('## Raw Data')
    st.table(vax_df)

except URLError as e:
    st.error(
        """
        **This App requires internet access.**

        Connection error: %s
    """
        % e.reason
    )

progress_bar.empty()
progress_message.empty()
# st.button("Re-run")
