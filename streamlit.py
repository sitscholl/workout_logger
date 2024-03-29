import streamlit as st
import pandas as pd
import numpy as np
from collections import defaultdict
from _functions import to_df, call_notion, push_notion, agg_table
from notion_client import Client
import datetime
from datetime import date
from datetime import time
import asyncio
import gspread
from gspread_dataframe import set_with_dataframe
import calendar

def to_s(t):
    
    m,s,ms = str(t).split(':')
    s = int( int(m)*60 + int(s) + int(float(ms))/1000 )
    
    return(s)
    
async def start_timer(ph, s):

    while s > 0:
        mm, ss = s//60, s%60
        ph.metric("Countdown", f"{mm:02d}:{ss:02d}")
        dummy = await asyncio.sleep(1)
        
        s-= 1
        
        if stop:
            break
            
def autoplay_audio(url = "https://www.orangefreesounds.com/wp-content/uploads/2022/04/Small-bell-ringing-short-sound-effect.mp3"):

    md = f"""
        <audio autoplay="true">
        <source src="{url}" type="audio/mp3">
        </audio>
        """
    st.markdown(
        md,
        unsafe_allow_html=True,
    )
 
st.set_page_config(
    page_title="Workout Logger",
    page_icon="🏋️‍♀️",
    initial_sidebar_state="collapsed"
)

token = st.secrets['token']
log_id = st.secrets['log_id']
exercises_id = st.secrets['exercises_id']
workouts_id = st.secrets['workouts_id']

notion = Client(auth=token)

@st.cache()
def get_notion(token, db_id, query_filter = None):
    db_raw = call_notion(token, db_id, query_filter)
    return(to_df(db_raw['results']))

@st.cache(allow_output_mutation = True)
def get_mutable():
    return []

@st.cache(allow_output_mutation = True)
def get_end_time():
    return [None]

@st.cache(allow_output_mutation = True)
def get_bodyweight():
    return [np.nan]

corr_df = pd.DataFrame([['Concentric', 1],  ['Eccentric', 3], ['Isometric', 2]], 
                          columns = ['Type', 'corr'])
wo_tbl_cols = ['Order', 'Exercise Name', 'Set', 'Weight', 'Distance', 'Reps', 'RPE', 'Failure', 'Notes']

# --- Import Datasets ---
#TODO: Use Parent Exercise column (relation) to get parent exercise name instead of Parent column
ex_database = get_notion(token, exercises_id)[['Parent', 'Name', 'Level', 'Type', 'Group', 'Group 2', 'Category', 'Muscles', 'Status', 'page_id']]
ex_database = ex_database.sort_values(['Parent', 'Level', 'Name']).reset_index(drop = True)

active_exercises = ex_database.loc[ex_database['Status'].isin(['In Progress']), 'Name'].tolist()
accessory_exercises = ex_database.loc[ex_database['Status'].isin(['Accessory']), 'Name'].tolist()

#params = {i: defaultdict(lambda : np.nan) for i in ex_database['Name'].unique()}
params = defaultdict(lambda : np.nan)

# --- Initialize persistent variables ---  
    
mutable = get_mutable()
end_time = get_end_time()
bodyweight = get_bodyweight()
    
# --- App Layout ---
st.title('Workout Logger')

# --- Workout Level Input ---

st.markdown("### Workout Input")

c1, c2, c3, c4, c5 = st.tabs(['Name', 'Date', 'Bodyweight', 'Notes', 'Rating'])
with c1:
    wo_name = st.text_input('Workout Title', value = 'Strength')
with c2:
    wo_date = st.date_input('Workout Date', value = date.today())
with c3:
    bw = st.number_input('Bodyweight', step = 1.0, value = np.nan)       
with c4:
    workout_notes = st.text_input('Workout Notes:') 
with c5:
    workout_rating = st.number_input('Workout Rating', value = np.nan, min_value = 0.0, max_value = 10.0, step = 1.0)

if bw == bw:
    bodyweight[0] = bw
    
st.markdown('---')
                   
# --- Data Input Form ---  

st.markdown("### Exercise Input")

norder = len(mutable)+1
ex_options = active_exercises + accessory_exercises + [i for i in ex_database['Name'].unique() if i not in active_exercises]
ex = st.selectbox('Exercise', 
                  options = ex_options)
                  #index = ex_options.index(ex_default))
with st.form(ex):
        
    nset = len([i for i in mutable if i['Exercise Name'] == [ex]]) + 1

    st.markdown(f'**{ex}** (*Set {nset}*) (*Exercise Nr. {norder}*)')
    
    #params = last_wo.loc[(last_wo['Exercise Name'] == ex) & (last_wo['Set'] == nset)]
    #params = params.replace(0, np.nan).to_dict('records')[0]
    #params['Reps'] = float(params['Reps'])
    
    c1, c2 = st.columns(2)
    with c1:
        weight = st.number_input('Weight', key = f'Weight_{ex}', value = params['Weight'], step = .5)
        distance = st.number_input('Distance', key = f'Distance_{ex}', value = params['Distance'], step = .5)
        reps = st.number_input('Reps', key = f'Reps_{ex}', value = params['Reps'], step = 1.0)
        RPE = st.number_input('RPE', key = f'RPE_{ex}', value = params['RPE'], min_value = 0.0, max_value = 10.0, step = .5)      
        
    with c2:
        st.write('')
        st.write('')
        st.write('')
        
        failure = st.checkbox('To Failure?', key = f'Failure_{ex}')
        notes = st.text_input('Notes', key = f'Notes_{ex}')
        intens = st.selectbox('Intensity', key = f'Intensity_{ex}', options = ['Heavy', 'Light', 'Medium', ''], index = 3)
        timer = st.time_input('Timer', key = f'Timer_{ex}', value = time(2, 30))
        
    submitted = st.form_submit_button(f'Submit {ex}')
    
    if submitted and ((end_time[0] == None) or (end_time[0] < datetime.datetime.now())):                
        mutable.append({'Exercise Name': [ex], 'Set': [nset], 'Weight': [weight],
                            'Distance': [distance], 'Reps': [reps], 'RPE': [RPE],
                            'Failure': [failure], 'Intensity': intens, 'Notes': [notes], 
                            'Order': [norder], 'Rest': [to_s(timer)]})
        
        #Save the scheduled end time when the timer is started
        end_time[0] = datetime.datetime.now() + datetime.timedelta(seconds = to_s(timer))

# --- Timer ---  

ph = st.empty()
stop = st.button('Stop timer')

if stop:
    end_time[0] = None
    
st.markdown('---')
      
# --- Generate table for current workout ---

if len(mutable) > 0:
     wo_tbl = pd.concat([pd.DataFrame(i) for i in mutable])
else:
    wo_tbl = pd.DataFrame(columns = wo_tbl_cols)
   
agg_funcs = {'Set': lambda x: len(x), 'Reps': np.sum, 'RPE': np.mean}

wo_agg = wo_tbl.groupby('Exercise Name')[['Set', 'Reps', 'RPE']].agg(agg_funcs)

st.markdown('### Workout Overview')
st.caption(datetime.datetime.strftime(wo_date, '%Y-%m-%d'))
st.table(wo_agg.style.format(precision=1))
    
# --- Detailed Tables ---

with st.expander('Check detailed workout log'):
    st.dataframe(wo_tbl.sort_values(['Exercise Name', 'Set']).style.format(precision=1))
    
# --- Push Data to Notion ---

end_wo = st.sidebar.button('Finish Workout')
if end_wo:

    data_push = wo_tbl.merge(ex_database[['Name', 'page_id']].rename(columns = {'Name': 'Exercise Name'}),
                             on = 'Exercise Name', how = 'left', validate = 'many_to_one')
    
    try:
        r = push_notion(token = token, log_id = log_id, wo_id = workouts_id, 
                        data = data_push, wo_date = wo_date, wo_notes = workout_notes,
                        wo_rating = workout_rating, bodyweight = bodyweight[0], wo_name = wo_name)
        
        mutable.clear()
        bodyweight[0] = None
        st.success('🟢 Data succesfully send to notion!') 
        
        #st.experimental_rerun()
    except Exception as e:
        st.dataframe(data_push)
        st.write(e)
        st.error('⛔ Error during push_notion function. Please make sure all input variables are valid!')
        
    #Push aggregated table to google sheet
    #1 get data from notion
    month_start = f'{wo_date.year}-{wo_date.month:02}-01'

    wo_ids = call_notion(token, workouts_id, query_filter = {'property': 'Date', 'date': {'on_or_after': month_start}})
    wo_ids = [i['id'] for i in wo_ids['results']]

    log_call = [call_notion(token, log_id, query_filter = {'property': 'Workout', 'relation': {'contains': i}}) for i in wo_ids]
    tbl_log = pd.concat([to_df(i['results']) for i in log_call])
    
    df_out = agg_table(tbl_log)
    
    #2 send to google sheets
    try:
        scope = ["https://spreadsheets.google.com/feeds",'https://www.googleapis.com/auth/spreadsheets',"https://www.googleapis.com/auth/drive.file","https://www.googleapis.com/auth/drive"]

        creds = st.secrets["gcp_service_account"]
        client = gspread.service_account_from_dict(creds, scope)   
        gtable = client.open("Workout Summary")
        sheet_name = f"{calendar.month_abbr[wo_date.month]}{wo_date.year}"
        sheets = [i.title for i in gtable.worksheets()]

        if sheet_name not in sheets:
            gtable.duplicate_sheet(1765995081, new_sheet_name=sheet_name)
            #gtable.add_worksheet(sheet_name, rows = 100, cols = 100)
        else:
            gtable.worksheet(sheet_name).clear()

        ws = gtable.worksheet(sheet_name)

        set_with_dataframe(worksheet=ws, dataframe=df_out, include_index=True, include_column_header=True, resize=True)

        st.success('🟢 Data succesfully send to google sheet!') 
    except Exception as e:
        st.dataframe(df_out)
        st.write(e)
        st.error('⛔ Error during push_notion function. Please make sure all input variables are valid!')
    
# --- Reset Workout ---

clear_wo = st.sidebar.button('Clear Workout')
if clear_wo:
    mutable.clear()
    end_time[0] = None
    bodyweight[0] = None
    
    st.experimental_rerun()

        
# --- Timer ---
    
if (end_time[0] != None) and (end_time[0] > datetime.datetime.now()):
    #Get remaining seconds to scheduled end time
    t = int((end_time[0] - datetime.datetime.now()).total_seconds())
    
    asyncio.run(start_timer(ph, t))
    
    autoplay_audio()
    
    ph.empty()
    end_time[0] = None
