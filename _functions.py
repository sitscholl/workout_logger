import sys
import warnings
from collections import defaultdict
import pandas as pd
from notion_client import Client

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