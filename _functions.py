import sys
import warnings
from collections import defaultdict
import pandas as pd
from notion_client import Client
#import gspread
import datetime
import re

def push_notion(token, log_id, wo_id, data, wo_date, wo_notes, wo_rating, bodyweight, wo_name):
    
    notion = Client(auth=token)
    
    if not isinstance(wo_date, str):
        wo_date = wo_date.strftime('%Y-%m-%d')
    
    #Check if workout entry exists
    #wo_row = call_notion(token, wo_id, query_filter = {'property': 'Date', 'date': {'equals': wo_date}})
    
    #if len(wo_row['results']) == 0:
    #Create workout entry
    properties = {
        "Name": {"title": [{"text": {"content": wo_name}}]},
        "Date": {"date": {"start": wo_date}},
        "Notes": {'rich_text':[{'type': 'text', 'text': {'content': wo_notes}}]},
        "Rating num": {"type": "number", "number": wo_rating},
        "Bodyweight": {"type": "number", "number": bodyweight}
        }

    if (bodyweight != bodyweight) or (bodyweight is None):
        del properties['Bodyweight']
    if (wo_rating != wo_rating) or (wo_rating is None):
        del properties['Rating num']

    workout_push = notion.pages.create(parent={"database_id": wo_id}, properties=properties)
    wo_page_id = workout_push['id']
        
    #else:
    #    wo_page_id = wo_row['results'][0]['id']
    
    data_fill = data.copy()
    for c in data.select_dtypes('number'):
        data_fill[c] = data_fill[c].fillna(0).astype(float)
          
    #push exercises to exercise_log
    for i in data_fill.index:
        
        row = data_fill.loc[i]
        # Create a new page in notion
        properties = {
            "Name": {"title": [{"text": {"content": row['Exercise Name']}}]},
            "Set": {"type": "number", "number": row['Set']},
            "Weight": {"type": "number", "number": row['Weight']},
            "Distance": {"type": "number", "number": row['Distance']},
            "Reps": {"type": "number", "number": row['Reps']},
            "RPE": {"type": "number", "number": row['RPE']},
            "Order": {"type": "number", "number": row['Order']},
            "Rest": {"type": "number", "number": row['Rest']},
            "Notes": {'rich_text':[{'type': 'text', 'text': {'content': row['Notes']}}]},
            "Failure": {'checkbox': bool(row['Failure'])},
            "Exercise": {
                "relation": [{"id": row['page_id']}]
                },
            "Workout": {
                "relation": [{'id': wo_page_id}]
                }
        }
        
        for i in ['Weight', 'Distance', 'RPE', 'Reps']:
            if (row[i] == 0) or (row[i] != row[i]) or (row[i] is None):
                del properties[i]
    
        log_push = notion.pages.create(parent={"database_id": log_id}, properties=properties)
        
# def push_gsheet(creds, log_id):
    
#     #Save backup to google sheets
#     scope = ["https://spreadsheets.google.com/feeds",'https://www.googleapis.com/auth/spreadsheets',"https://www.googleapis.com/auth/drive.file","https://www.googleapis.com/auth/drive"]
#     client = gspread.service_account_from_dict(creds, scope)
#     sheet = client.open("Wo Backup").sheet1
#     #gcols = sheet.row_values(1)
    
#     tbl_full = call_notion(token, log_id) #Download entire dataset

#     for c in tbl_full.select_dtypes(np.number).columns:
#         tbl_full[c] = tbl_full[c].fillna(0).astype(float)
        
#     sheet.clear()
         
#     tbl_full.drop('Mesocycle', axis = 1, inplace = True, errors = 'ignore') #Fix values of mesocycle
#     sheet.append_rows([tbl_full.columns.tolist()]) #Add column titles
#     sheet.append_rows(tbl_full.values.tolist(), value_input_option="USER_ENTERED") #Add data

def call_notion(token, dbid, query_filter = None):
    
    notion = Client(auth=token)

    query_post = {"database_id": dbid}
    query_ret = notion.databases.query(**query_post, filter = query_filter)
    
    next_cur = query_ret["next_cursor"]
    while query_ret["has_more"]:
          query_post["start_cursor"] = next_cur
          db_query_ret = notion.databases.query(**query_post)
          
          next_cur = db_query_ret["next_cursor"]
          query_ret["results"] += db_query_ret["results"]
          
          if next_cur is None:
              break
      
    return(query_ret)

def to_df(results):

    included_types = ['checkbox',
      'date',
      'multi_select',
      'number',
      'relation',
      'rollup',
      'select',
      'title',
      'created_time',
      'formula',
      'rich_text']
    
    d = defaultdict(list)
    for row in results:
        
        props = row['properties']
        pid = row['id']
        d['page_id'].append(pid)
        for col in props.keys():
            val = None
            ctype = props[col]['type']

            if ctype not in included_types:
                warnings.warn(f'Unknown ctype! Please include {ctype} into function definition.')
            
            if ctype in ['checkbox', 'number', 'created_time']:
                val = props[col][ctype]
            
            if ctype == 'date': #Only extracts start date. modify here if end date also needed
                if props[col][ctype] != None:
                    val = props[col][ctype]['start']
                else:
                    val = None
                
            if ctype == 'multi_select':
                val = [i['name'] for i in props[col][ctype]]
                if len(val) == 0:
                    val = None
                else:
                    val = ', '.join(val)
            
            if ctype == 'relation':
                val = [i['id'] for i in props[col][ctype]]
                if len(val) == 1:
                    val = val[0]
                else:
                    val = ', '.join(val)
                
            if ctype == 'select':
                if props[col][ctype] != None:
                    val = props[col][ctype]['name']
                else:
                    val = None
            
            if ctype == 'title':
                
                if len(props[col][ctype]) > 0:
                    ctype2 = props[col][ctype][0]['type']
                    val = props[col][ctype][0][ctype2]['content']
                else:
                    val = None
               
            if ctype == 'formula':
                ctype2 = props[col][ctype]['type']
                
                if ctype2 == 'date':
                    if props[col][ctype][ctype2] != None:
                        val = props[col][ctype][ctype2]['start']
                    else:
                        val = None
                elif ctype2 == 'number':
                    val = props[col][ctype][ctype2]
                else:
                    print(col)
                    print(ctype2)
                    warnings.warn('Undefined ctype in formula! Modify function to_df().')
            
            if ctype == 'rich_text':
                
                if len(props[col][ctype]) > 0:
                    ctype2 = props[col][ctype][0]['type']
                    val = props[col][ctype][0][ctype2]['content']
                else:
                    val = None
                    
            if ctype == 'rollup':
                
                ctype2 = props[col][ctype]['type']
                
                if ctype2 == 'date':
                    if props[col][ctype][ctype2] == None:
                        val = None
                    else:
                        val = props[col][ctype][ctype2]['start']
                    
                elif ctype2 == 'number':
                    val = props[col][ctype][ctype2]
                    
                else:
                    ctype3 = props[col][ctype][ctype2]

                    if len(ctype3) > 1:
                        sys.exit('Len of ctype 3 is greater than 1! Check for potential errors')
                    else:
                        ctype3 = ctype3[0]['type']
                    
                    if ctype3 == 'multi_select':
                        l = props[col][ctype][ctype2][0][ctype3]
                        val = [i['name'] for i in l]
                        
                        if len(val) == 0:
                            val = None
                        else:
                            val = ', '.join(val)
                    
                    if ctype3 == 'relation':
                        val = props[col][ctype][ctype2][0][ctype3]
                      
                    if ctype3 == 'select':
                        dic = props[col][ctype][ctype2][0][ctype3]
                        if dic != None:
                            val = props[col][ctype][ctype2][0][ctype3]['name']
                        else:
                            val = None
                            
                    if ctype3 == 'title':
                        ctype4 = props[col][ctype][ctype2][0][ctype3][0]['type']
                        val = props[col][ctype][ctype2][0][ctype3][0][ctype4]['content']
                        
                    if ctype3 == 'date':
                        if props[col][ctype][ctype2][0][ctype3] == None:
                            val = None
                        else:
                            val = props[col][ctype][ctype2][0][ctype3]['start']
               
            d[col].append(val)
    df = pd.DataFrame(d)
    return(df)

def create_string(weight, distance, n, reps, failure):
    
    failure = '*' if failure else ''
    distance = re.sub('\.0', '', distance)
    weight = re.sub('\.0', '', weight)

    str_list = [str(i) for i in [weight, distance, n, reps] if i != '']
    str_agg = 'x'.join(str_list)
    return(str_agg)

def agg_table(tbl_log):

    #Prepare table
    tbl_log['Date'] = pd.to_datetime(tbl_log['Date'], format = '%Y-%m-%d')
    #tbl_log = tbl_log.loc[tbl_log['Category'] == 'Strength']
    tbl_log = tbl_log[['Date', 'Order', 'Parent', 'Name', 'Set', 'Weight', 'Distance', 'Reps', 'Failure', 'RPE']].copy()
    tbl_log.sort_values(['Date', 'Order', 'Name', 'Set'], inplace = True)

    #Transform numbers to strings
    for i, unit in zip(['Weight', 'Distance'], ['kg', 'cm']):
        tbl_log[i] = tbl_log[i].fillna('').astype(str)
        #tbl_log[i] = np.where(tbl_log[i] != '', tbl_log[i] + unit, tbl_log[i])
    tbl_log['Reps'] = tbl_log['Reps'].astype(int)

    #Calculate metrics for each workout
    tbl_log = tbl_log.groupby(['Date', 'Parent', 'Name', 'Weight', 'Distance', 'Reps']).agg(n = ('Set', len), failure = ('Failure', lambda x: any(x == True)), order = ('Order', min)).reset_index()
    tbl_log['n'] = tbl_log['n'].astype(int)

    #Create aggregated string
    tbl_log['agg_str'] = tbl_log.apply(lambda row: create_string(row['Weight'], row['Distance'], row['n'], row['Reps'], row['failure']), axis = 1)

    tbl_log = tbl_log.sort_values(['Date', 'order']).groupby(['Date', 'Parent', 'Name'], as_index=False).agg(agg_string = ('agg_str', lambda x: ';\n'.join(x)), order = ('order', min))
    tbl_log.sort_values(['Date', 'order'], inplace = True)

    #Add timestamp columns
    tbl_log['date'] = tbl_log['Date'].dt.date
    tbl_log['week'] = tbl_log.Date.dt.isocalendar().week
    tbl_log['day_of_week'] = tbl_log['Date'].dt.day_name()
    #tbl_log['day_of_week'] = tbl_log['date'].astype(str) + '\n' + tbl_log['day_of_week']
    #tbl_log['agg_string'] = tbl_log['Name'] + ' ' + tbl_log['agg_string']

    #Pivot
    df_out = log_re.pivot_table(index = ['Parent', 'Name'], columns = ['week', 'date', 'day_of_week'], 
                             values = 'agg_string', aggfunc = lambda x: '; '.join(x))

    return(df_out)
