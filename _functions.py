import sys
import warnings
from collections import defaultdict
import pandas as pd
from notion_client import Client
import gspread
import datetime

def push_notion(token, log_id, wo_id, data, wo_date, wo_notes, wo_rating, bodyweight):
    
    notion = Client(auth=token)
    
    if not isinstance(wo_date, str):
        wo_date = wo_date.strftime('%Y-%m-%d')
    
    #Check if workout entry exists
    wo_row = call_notion(token, wo_id, query_filter = {'property': 'Date', 'date': {'equals': wo_date}})
    
    if len(wo_row['results']) == 0:
        #Create workout entry
        properties = {
            "Name": {"title": [{"text": {"content": 'Strength'}}]},
            "Date": {"date": {"start": wo_date}},
            "Notes": {'rich_text':[{'type': 'text', 'text': {'content': wo_notes}}]},
            "Rating num": {"type": "number", "number": wo_rating},
            "Bodyweight": {"type": "number", "number": bodyweight}
            }
        
        workout_push = notion.pages.create(parent={"database_id": wo_id}, properties=properties)
        wo_page_id = workout_push['id']
        
    else:
        wo_page_id = wo_row['results'][0]['id']
    
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
                else:
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
                    
                    print(col)
                    print(props[col][ctype])

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
               
            d[col].append(val)
    df = pd.DataFrame(d)
    return(df)
