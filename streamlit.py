import streamlit as st
import pandas as pd
import numpy as np
from collections import defaultdict
from _functions import to_df, call_notion, push_notion
from notion_client import Client
import datetime
from datetime import date
from datetime import time
import asyncio
import altair as alt
# import gspread

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

token = st.secrets['token']
log_id = st.secrets['log_id']
exercises_id = st.secrets['exercises_id']
workouts_id = st.secrets['workouts_id']

google_credentials = st.secrets['g_creds']

notion = Client(auth=token)

@st.cache(ttl = 86400)
def get_notion(token, db_id, query_filter = None):
    db_raw = call_notion(token, db_id, query_filter)
    return(to_df(db_raw['results']))

##Use Parent Exercise column (relation) to get parent exercise name instead of Parent column
ex_database = get_notion(token, exercises_id)[['Parent', 'Name', 'Level', 'Type', 'Group', 'Group 2', 'Category', 'Muscles', 'Status', 'page_id']]
ex_database = ex_database.sort_values(['Parent', 'Level', 'Name']).reset_index(drop = True)

ex_log = get_notion(token, log_id, query_filter = {'property': 'Date', 'rollup': {'date': {'past_month': {}}}})
ex_log = ex_log[['Date', 'Exercise Name', 'Exercise', 'Set', 'Weight', 'Distance', 'Reps', 'RPE', 'Failure', 'Type', 'Parent', 'Group', 'Group 2', 'Status', 'Mesocycle', 'Notes']].copy()
ex_log['Date'] = pd.to_datetime(ex_log['Date'], format = '%Y-%m-%d')
ex_log.sort_values(['Date', 'Exercise Name'], inplace = True)
ex_log['Set_fill'] = ex_log.groupby(['Date', 'Exercise Name'])['Set'].cumcount()+1
ex_log['Set'] = ex_log['Set'].fillna(ex_log['Set_fill']).astype(int)
ex_log = ex_log.sort_values(['Date', 'Exercise Name', 'Set']).reset_index(drop = True)

active_exercises = ex_database.loc[ex_database['Status'].isin(['In Progress']), 'Name'].tolist()
accessory_exercises = ex_database.loc[ex_database['Status'].isin(['Accessory']), 'Name'].tolist()

if "sets" not in st.session_state.keys():
    set_dict = {i: 1 for i in ex_database['Name'].unique()}
    st.session_state.sets = set_dict
    
if 'order' not in st.session_state.keys():
    st.session_state.order = 1
    
if "defaults" not in st.session_state.keys():
    ex_defaults = {i: defaultdict(lambda : np.nan) for i in ex_database['Name'].unique()}
    st.session_state.defaults = ex_defaults
    
if "end_time" not in st.session_state.keys():
    st.session_state.end_time = None
    
#### App layout
st.title('Workout Logger')

st.write(st.session_state.order)
       
c1, c2 = st.columns([1, 4])
with c1:
    with st.expander('Change Date'):
        wo_date = st.date_input('Workout Date', value = date.today())
        
wo_tbl_cols = ['Order', 'Exercise Name', 'Set', 'Weight', 'Distance', 'Reps', 'RPE', 'Failure', 'Notes']
wo_tbl = call_notion(token, log_id, query_filter = {'property': 'Date', 'rollup': {'date': {'equals': datetime.datetime.strftime(wo_date, '%Y-%m-%d')}}})

if len(wo_tbl['results']) == 0:
    wo_tbl = pd.DataFrame(columns = wo_tbl_cols)
else:
    wo_tbl = to_df(wo_tbl['results'])[wo_tbl_cols]
    wo_tbl.sort_values('Order', inplace = True)
          
ex = st.selectbox('Exercise', options = active_exercises + accessory_exercises + [i for i in ex_database['Name'].unique() if i not in active_exercises])
with st.form(ex):
        
    nset = st.session_state.sets[ex]

    st.markdown(f'**{ex}** (*Set {nset}*)')
    
    c1, c2 = st.columns(2)
    with c1:
        weight = st.number_input('Weight', value = st.session_state.defaults[ex]['Weight'], step = .5)
        reps = st.number_input('Reps', value = st.session_state.defaults[ex]['Reps'], step = 1.0)
        failure = st.checkbox('To Failure?')
        
        st.write("")
        st.write("")
        timer = st.time_input('Timer', value = time(2, 30))
        
    with c2:
        distance = st.number_input('Distance', value = st.session_state.defaults[ex]['Distance'], step = .5)
        RPE = st.number_input('RPE', value = st.session_state.defaults[ex]['RPE'], min_value = 0.0, max_value = 10.0, step = .5)
        notes = st.text_input('Notes')
        
        st.write("")
        submitted = st.form_submit_button('Submit')
    
    if submitted:
        
        data_new = pd.DataFrame({'Exercise': [ex], 'Set': [nset], 'Weight': [weight],
                                 'Distance': [distance], 'Reps': [reps], 'RPE': [RPE],
                                 'Failure': [failure], 'Notes': [notes], 
                                 'Order': [st.session_state.order], 'Rest': [to_s(timer)]})
        data_new = data_new.merge(ex_database[['Name', 'page_id']].rename(columns = {'Name': 'Exercise'}),
                                  on = 'Exercise', how = 'left', validate = 'many_to_one')
        
        st.session_state.defaults[ex].update({'Weight': weight, 'Distance': distance, 
                                              'Reps': reps, 'RPE': RPE})
        
        push_notion(token = token, log_id = log_id, wo_id = workouts_id, 
                    data = data_new, wo_date = wo_date)
        
        st.session_state.sets[ex] += 1
        st.session_state.order += 1
        
        #Save the scheduled end time when the timer is started
        st.session_state.end_time = datetime.datetime.now() + datetime.timedelta(seconds = to_s(timer))

ph = st.empty()
stop = st.button('Stop timer')

if stop:
    st.session_state.end_time = None

col1, col2 = st.columns(2)
agg_funcs = {'Set': lambda x: len(x), 'Reps': np.sum, 'RPE': np.mean}
with col1:
    st.markdown('### This Workout')
    st.caption(datetime.datetime.strftime(wo_date, '%Y-%m-%d'))
    st.table(wo_tbl.groupby('Exercise Name')['Set', 'Reps', 'RPE'].agg(agg_funcs).style.format(precision=1))
    
with col2:
    last_wo_date = ex_log.loc[ex_log['Date'].dt.date != wo_date, 'Date'].max()
    st.markdown('### Last Workout')
    st.caption(datetime.datetime.strftime(last_wo_date, '%Y-%m-%d'))
    
    last_wo = ex_log.loc[ex_log['Date'] == last_wo_date, ['Exercise Name', 'Set', 'Weight', 'Distance', 'Reps', 'RPE', 'Failure', 'Notes']]
    st.table(last_wo.groupby('Exercise Name')['Set', 'Reps', 'RPE'].agg(agg_funcs).style.format(precision=1))
    
log_agg = ex_log.groupby(['Date', 'Exercise Name'], as_index = False)['Reps'].sum()

c = alt.Chart(log_agg).mark_line(point=True).encode(
  alt.Y('Reps:Q'),
  x='Date:T',
  color='Exercise Name:N'
)
st.altair_chart(c, use_container_width=True)

st.markdown('---')

workout_notes = st.text_input('Workout Notes:')  

st.markdown('---')

with st.expander('Check workout log'):
    st.dataframe(wo_tbl)
    
with st.expander('Check last workout'):
    st.dataframe(last_wo)
    
if (st.session_state.end_time != None) and (st.session_state.end_time > datetime.datetime.now()):
    #Get remaining seconds to scheduled end time
    t = int((st.session_state.end_time - datetime.datetime.now()).total_seconds())
    
    asyncio.run(start_timer(ph, t))
    
    ph.empty()
    st.session_state.end_time = None
