import streamlit as st
import pandas as pd
import numpy as np
from collections import defaultdict
from _functions import to_df, call_notion
from notion_client import Client
import datetime
from datetime import date
import gspread

token = st.secrets['token']
log_id = st.secrets['log_id']
exercises_id = st.secrets['exercises_id']
workouts_id = st.secrets['workouts_id']

google_credentials = st.secrets['g_creds']

notion = Client(auth=token)

def add_vals(exercise, data):
    st.session_state.tbl = pd.concat([st.session_state.tbl, data]).reset_index(drop = True)

@st.cache(ttl = 86400)
def get_notion(token, db_id):
    db_raw = call_notion(token, db_id)
    return(to_df(db_raw['results']))

def get_notion2(token, db_id):
    db_raw = call_notion(token, db_id)
    return(to_df(db_raw['results']))

##Use Parent Exercise column (relation) to get parent exercise name instead of Parent column
ex_database = get_notion(token, exercises_id)[['Parent', 'Name', 'Level', 'Type', 'Group', 'Group 2', 'Category', 'Muscles', 'Status', 'page_id']]
ex_database = ex_database.sort_values(['Parent', 'Level', 'Name']).reset_index(drop = True)

ex_log = get_notion(token, log_id)[['Date', 'Exercise Name', 'Exercise', 'Set', 'Weight', 'Distance', 'Reps', 'RPE', 'Failure', 'Type', 'Parent', 'Group', 'Group 2', 'Status', 'Mesocycle', 'Notes']]
ex_log['Date'] = pd.to_datetime(ex_log['Date'], format = '%Y-%m-%d')
ex_log.sort_values(['Date', 'Exercise Name'], inplace = True)
ex_log['Set_fill'] = ex_log.groupby(['Date', 'Exercise Name'])['Set'].cumcount()+1
ex_log['Set'] = ex_log['Set'].fillna(ex_log['Set_fill']).astype(int)
ex_log = ex_log.sort_values(['Date', 'Exercise Name', 'Set']).reset_index(drop = True)

active_exercises = ex_database.loc[ex_database['Status'].isin(['In Progress', 'Accessory']), 'Name'].tolist()

st.title('Workout log')
cap = st.container()

tbl_empty = pd.DataFrame(columns = ['Exercise', 'Set', 'Weight', 'Distance', 'Reps', 'RPE', 'Failure', 'Notes'])
if "tbl" not in st.session_state.keys():
    st.session_state.tbl = tbl_empty

set_dict = {i: 1 for i in ex_log['Exercise Name'].unique()}

if "sets" not in st.session_state.keys():
    st.session_state.sets = set_dict
    
ex_defaults = {i: defaultdict(lambda : np.nan) for i in ex_log['Exercise Name'].unique()}

if "defaults" not in st.session_state.keys():
    st.session_state.defaults = ex_defaults

with st.sidebar:
       
    ex = st.selectbox('Exercise', options = active_exercises + [i for i in ex_log['Exercise Name'].unique() if i not in active_exercises])
    
    with st.form(ex):
            
        nset = st.session_state.sets[ex]

        st.markdown(f'**{ex}** (*Set {nset}*)')
        weight = st.number_input('Weight', value = st.session_state.defaults[ex]['Weight'], step = .5)
        distance = st.number_input('Distance', value = st.session_state.defaults[ex]['Distance'], step = .5)
        reps = st.number_input('Reps', value = st.session_state.defaults[ex]['Reps'], step = 1.0)
        RPE = st.number_input('RPE', value = st.session_state.defaults[ex]['RPE'], min_value = 0.0, max_value = 10.0, step = .5)
        failure = st.checkbox('To Failure?')
        notes = st.text_input('Notes')

        submitted = st.form_submit_button('Submit')
        
        if submitted:
            st.session_state.sets[ex] += 1
            add_vals(exercise = ex, 
                     data = pd.DataFrame({'Exercise': [ex], 'Set': [nset], 'Weight': [weight],
                                          'Distance': [distance], 'Reps': [reps], 'RPE': [RPE],
                                          'Failure': [failure], 'Notes': [notes]}))
            
            st.session_state.defaults[ex].update({'Weight': weight, 'Distance': distance, 
                                                  'Reps': reps, 'RPE': RPE})
            
    workout_notes = st.text_input('Workout Notes:')
    with st.expander('Change Date'):
        wo_date = st.date_input('Workout Date', value = date.today())
    
    upload = st.button('Upload')
    reset = st.button('Reset')

cap = st.caption(ex)

if reset:
    st.session_state.tbl = tbl_empty
    
    for key in st.session_state.sets.keys():
        st.session_state.sets[key] = 1
        
    st.experimental_rerun()

st.markdown('## This Workout:')
 
col1, col2, col3 = st.columns([3, 1, 1])

tbl_sub = st.session_state.tbl.loc[st.session_state.tbl['Exercise'] == ex].set_index('Set')
col1.dataframe(tbl_sub.dropna(how = 'all', axis = 1).drop('Exercise', axis = 1, errors = 'ignore').style.format({'Weight': '{:.1f}', 'Distance': '{:.1f}', 'RPE': '{:.1f}', 'Reps': '{:.1f}'}))
col2.markdown('Total Volume')
col2.text(tbl_sub['Reps'].sum())
col2.markdown('Average RPE')
col2.text(np.round(tbl_sub['RPE'].mean(), 1))
col3.markdown('Date')
col3.text(datetime.datetime.strftime(wo_date, '%Y-%m-%d'))

st.markdown('---')
st.markdown('## Last Workout:')

col1, col2, col3 = st.columns([3, 1, 1])

last_wo = ex_log.loc[ex_log['Exercise Name'] == ex]
last_wo_date = last_wo['Date'].max()
last_wo = last_wo.loc[last_wo['Date'] == last_wo_date, ['Set', 'Weight', 'Distance', 'Reps', 'RPE', 'Failure', 'Notes']].set_index('Set')
col1.dataframe(last_wo.dropna(how = 'all', axis = 1).drop('Exercise', axis = 1, errors = 'ignore').style.format({'Weight': '{:.1f}', 'Distance': '{:.1f}', 'RPE': '{:.1f}'}))
col2.markdown('Total Volume')
col2.text(last_wo['Reps'].sum())
col2.markdown('Average RPE')
col2.text(np.round(last_wo['RPE'].mean(), 1))
col3.markdown('Date')
col3.text(datetime.datetime.strftime(last_wo_date, '%Y-%m-%d'))
   
st.markdown('---')

tbl_export = st.session_state.tbl.copy()
tbl_export = pd.merge(tbl_export, ex_database[['Name', 'page_id']].rename(columns = {'Name': 'Exercise'}),
                      on = 'Exercise', how = 'left', validate = 'many_to_one')

with st.expander('Check all records'):
    st.dataframe(tbl_export)  
    
if upload:
    tbl_fill = tbl_export.copy()
    for c in ['Weight', 'Distance', 'RPE']:
        tbl_fill[c] = tbl_fill[c].fillna(0).astype(float)
        
    #Create workout entry
    wo_date_str = wo_date.strftime('%Y-%m-%d')
    properties = {
        "Name": {"title": [{"text": {"content": 'Strength'}}]},
        "Date": {"date": {"start": wo_date_str}},
        "Notes": {'rich_text':[{'type': 'text', 'text': {'content': workout_notes}}]}
        }
    
    workout_push = notion.pages.create(parent={"database_id": workouts_id}, properties=properties)
    wo_id = workout_push['id']
        
    #push exercises to exercise_log
    for i in tbl_fill.index:
        
        row = tbl_fill.loc[i]
        # Create a new page in notion
        properties = {
            "Name": {"title": [{"text": {"content": row['Exercise']}}]},
            "Set": {"type": "number", "number": row['Set']},
            "Weight": {"type": "number", "number": row['Weight']},
            "Distance": {"type": "number", "number": row['Distance']},
            "Reps": {"type": "number", "number": row['Reps']},
            "RPE": {"type": "number", "number": row['RPE']},
            "Notes": {'rich_text':[{'type': 'text', 'text': {'content': row['Notes']}}]},
            "Failure": {'checkbox': row['Failure']},
            "Exercise": {
                "relation": [{"id": row['page_id']}]
                },
            "Workout": {
                "relation": [{'id': wo_id}]
                }
        }
    
        log_push = notion.pages.create(parent={"database_id": log_id}, properties=properties)
        
    #Save backup to google sheets
    scope = ["https://spreadsheets.google.com/feeds",'https://www.googleapis.com/auth/spreadsheets',"https://www.googleapis.com/auth/drive.file","https://www.googleapis.com/auth/drive"]
    client = gspread.service_account_from_dict(google_credentials, scope)
    sheet = client.open("Wo Backup").sheet1
    #gcols = sheet.row_values(1)
    
    tbl_full = get_notion2(token, log_id) #Download entire dataset

    for c in tbl_full.select_dtypes(np.number).columns:
        tbl_full[c] = tbl_full[c].fillna(0).astype(float)
         
    tbl_full.drop('Mesocycle', axis = 1, inplace = True, errors = 'ignore') #Fix values of mesocycle
    sheet.append_rows([tbl_full.columns.tolist()]) #Add column titles
    sheet.append_rows(tbl_full.values.tolist(), value_input_option="USER_ENTERED") #Add data