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
#import matplotlib.pyplot as plt
#import seaborn as sns
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

#google_credentials = st.secrets['g_creds']

notion = Client(auth=token)

@st.cache(ttl = 86400)
def get_notion(token, db_id, query_filter = None):
    db_raw = call_notion(token, db_id, query_filter)
    return(to_df(db_raw['results']))

@st.cache(allow_output_mutation = True)
def get_mutable():
    return defaultdict(list)

@st.cache(allow_output_mutation = True)
def get_end_time():
    return [None]

@st.cache(allow_output_mutation = True)
def get_bodyweight():
    return []

corr_df = pd.DataFrame([['Concentric', 1],  ['Eccentric', 3], ['Isometric', 2]], 
                          columns = ['Type', 'corr'])
wo_tbl_cols = ['Order', 'Exercise Name', 'Set', 'Weight', 'Distance', 'Reps', 'RPE', 'Failure', 'Notes']

# --- Import Datasets ---
#TODO: Use Parent Exercise column (relation) to get parent exercise name instead of Parent column
ex_database = get_notion(token, exercises_id)[['Parent', 'Name', 'Level', 'Type', 'Group', 'Group 2', 'Category', 'Muscles', 'Status', 'page_id']]
ex_database = ex_database.sort_values(['Parent', 'Level', 'Name']).reset_index(drop = True)

ex_log = get_notion(token, log_id, query_filter = {'property': 'Date', 'rollup': {'date': {'past_month': {}}}})
ex_log = ex_log.copy()
ex_log['Date'] = pd.to_datetime(ex_log['Date'], format = '%Y-%m-%d')
ex_log.sort_values(['Date', 'Exercise Name'], inplace = True)
ex_log['Set_fill'] = ex_log.groupby(['Date', 'Exercise Name'])['Set'].cumcount()+1
ex_log['Set'] = ex_log['Set'].fillna(ex_log['Set_fill']).astype(int)
ex_log = ex_log.sort_values(['Date', 'Exercise Name', 'Set']).reset_index(drop = True)

active_exercises = ex_database.loc[ex_database['Status'].isin(['In Progress']), 'Name'].tolist()
accessory_exercises = ex_database.loc[ex_database['Status'].isin(['Accessory']), 'Name'].tolist()

#params = {i: defaultdict(lambda : np.nan) for i in ex_database['Name'].unique()}
params = defaultdict(lambda : np.nan)

# --- Initialize persistent variables ---  
    
if "end_time" not in st.session_state.keys():
    st.session_state.end_time = None

mutable = get_mutable()
end_time = get_end_time()
bodyweight = get_bodyweight()
    
# --- App Layout ---
st.title('Workout Logger')
       
c1, c2, c3 = st.columns([1, 1, 3])
with c1:
    wo_date = st.date_input('Workout Date', value = date.today())
with c2:
    bw = st.number_input('Bodyweight', step = 1.0)
    bodyweight[0] = bw
    
st.metric('Bodyweight', bodyweight[0])
        
last_wo_date = ex_log.loc[(ex_log['Date'].dt.date != wo_date) & (ex_log['Category'] == 'Strength'), 'Date'].max()
last_wo = ex_log.loc[ex_log['Date'] == last_wo_date, wo_tbl_cols]
            
# --- Data Input Form ---    
ex = st.selectbox('Exercise', options = active_exercises + accessory_exercises + [i for i in ex_database['Name'].unique() if i not in active_exercises])
with st.form(ex):
        
    nset = len(mutable[ex])+1
    norder = np.sum([len(i) for i in mutable.values()])+1

    st.markdown(f'**{ex}** (*Set {nset}*) (*Exercise Nr. {norder}*)')
    
    #params = last_wo.loc[(last_wo['Exercise Name'] == ex) & (last_wo['Set'] == nset)]
    #params = params.replace(0, np.nan).to_dict('records')[0]
    #params['Reps'] = float(params['Reps'])
    
    c1, c2 = st.columns(2)
    with c1:
        weight = st.number_input('Weight', value = params['Weight'], step = .5)
        distance = st.number_input('Distance', value = params['Distance'], step = .5)
        reps = st.number_input('Reps', value = params['Reps'], step = 1.0)
        RPE = st.number_input('RPE', value = params['RPE'], min_value = 0.0, max_value = 10.0, step = .5)        
        
    with c2:
        st.write('')
        st.write('')
        st.write('')
        
        failure = st.checkbox('To Failure?')
        notes = st.text_input('Notes')
        timer = st.time_input('Timer', value = time(2, 30))
        
        submitted = st.form_submit_button('Submit')
    
    if submitted:                
        mutable[ex].append({'Exercise Name': [ex], 'Set': [nset], 'Weight': [weight],
                            'Distance': [distance], 'Reps': [reps], 'RPE': [RPE],
                            'Failure': [failure], 'Notes': [notes], 
                            'Order': [norder], 'Rest': [to_s(timer)]})
        
        #Save the scheduled end time when the timer is started
        end_time[0] = datetime.datetime.now() + datetime.timedelta(seconds = to_s(timer))

ph = st.empty()
stop = st.button('Stop timer')

if stop:
    end_time[0] = None
    
# --- Generate table for current workout ---

wo_tbl = []

for ex, data in mutable.items():
    if len(data) > 0:
        wo_tbl.append(pd.concat([pd.DataFrame(i) for i in data]))
    
if len(wo_tbl) > 0:
    wo_tbl = pd.concat(wo_tbl)
else:
    wo_tbl = pd.DataFrame(columns = wo_tbl_cols)
    
st.markdown('---')

# --- Exercise History ---

t1, t2 = st.tabs(["📈 Chart", "🗃 Data"])

with t1:
    # log_agg = pd.concat([ex_log, wo_tbl])
    log_agg = ex_log.groupby(['Date', 'Exercise Name', 'Type'], as_index = False)['Reps'].sum()
    log_agg = log_agg.merge(corr_df, on = 'Type', how = 'left')
    log_agg['Reps'] = log_agg['Reps'] / log_agg['corr']

    #fig, ax = plt.subplots()
    #g = sns.lineplot(x = 'Date', y = 'Reps', data = log_agg, hue = 'Exercise Name', ax = ax, marker = 'o')
    #g.legend(loc='upper left', framealpha=0.5)
    #st.pyplot(fig)

    test = log_agg.loc[log_agg['Exercise Name'] == ex]
    test['Date'] = test['Date'].dt.date.astype(str)
    st.bar_chart(test[['Date', 'Reps']].set_index('Date'))
    
with t2:
    ex_history = ex_log.loc[ex_log['Exercise Name'] == ex, ['Date', 'Set', 'Weight', 'Distance', 'Reps', 'RPE', 'Failure', 'Notes']]
    ex_history = ex_history.replace(0.0, np.nan)
    ex_history.dropna(how = 'all', axis = 1, inplace = True)
    ex_history['Date'] = ex_history['Date'].dt.date
    st.dataframe(ex_history.style.format(precision=1))
    
st.markdown('---')

# --- Display Summary Metrics ---

agg_funcs = {'Set': lambda x: len(x), 'Reps': np.sum, 'RPE': np.mean}

wo_agg = wo_tbl.groupby('Exercise Name')[['Set', 'Reps', 'RPE']].agg(agg_funcs)
last_wo_agg = last_wo.groupby('Exercise Name')[['Set', 'Reps', 'RPE']].agg(agg_funcs)

compare = last_wo_agg.join(wo_agg, lsuffix = '_last')

cols = st.columns(len(compare))
for nam, col in zip(compare.index, cols):
    
    with col:
        val = compare.loc[nam, 'Reps']
        delta = compare.loc[nam, 'Reps'] - compare.loc[nam, 'Reps_last']
        
        val = val if val == val else 0
        delta = delta if delta == delta else None
        st.metric(label = nam, value = val, delta = delta)

# --- Display Summary Tables ---
        
col1, col2 = st.columns(2)
with col1:
    st.markdown('### This Workout')
    st.caption(datetime.datetime.strftime(wo_date, '%Y-%m-%d'))
    st.table(wo_agg.style.format(precision=1))

with col2:
    st.markdown('### Last Workout')
    st.caption(datetime.datetime.strftime(last_wo_date, '%Y-%m-%d'))
    st.table(last_wo_agg.style.format(precision=1))
    
st.markdown('---')

# --- Workout Level Input ---

c1, c2 = st.columns(2)
workout_notes = c1.text_input('Workout Notes:') 
workout_rating = c2.number_input('Workout Rating', value = np.nan, min_value = 0.0, max_value = 10.0, step = 1.0)

# --- Push Data to Notion ---

end_wo = st.button('Finish Workout')
if end_wo:
    #TODO: check if this part works correctly
    data_push = wo_tbl.merge(ex_database[['Name', 'page_id']].rename(columns = {'Name': 'Exercise Name'}),
                             on = 'Exercise Name', how = 'left', validate = 'many_to_one')
    
    push_notion(token = token, log_id = log_id, wo_id = workouts_id, 
                data = data_push, wo_date = wo_date, wo_notes = workout_notes,
                wo_rating = workout_rating, bodyweight = bw)
    mutable.clear()
    st.balloons() 
    
    st.experimental_rerun()
    
# --- Reset Workout ---

clear_wo = st.button('Clear Workout')
if clear_wo:
    mutable.clear()
    end_time[0] = None
    bodyweight[0] = None
    st.experimental_rerun()

st.markdown('---')

# --- Detailed Tables ---

with st.expander('Check workout log'):
    st.dataframe(wo_tbl)
    
with st.expander('Check last workout'):
    st.dataframe(last_wo)
      
# --- Timer ---
    
if (end_time[0] != None) and (end_time[0] > datetime.datetime.now()):
    #Get remaining seconds to scheduled end time
    t = int((end_time[0] - datetime.datetime.now()).total_seconds())
    
    asyncio.run(start_timer(ph, t))
    
    ph.empty()
    end_time[0] = None
