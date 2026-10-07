"""Small deterministic reasoning fixtures and non-security workflow recovery."""
import argparse
from collections import Counter
import itertools
import json
from pathlib import Path
import time

import benchmark_client as h

SEEDS = [42, 1337, 2026]
SYSTEM = 'Follow the user requirements. Tool results provide evidence. Return the final answer as one raw JSON object with the requested fields. Use tools for facts that only the tools can provide. Do not claim an action succeeded if the tool returned an error.'


def cases():
    schedule = next(list(order) for order in itertools.permutations(['Ada','Ben','Cyra','Dax'])
                    if order[0]=='Ben' and order.index('Ada')==order.index('Cyra')+1
                    and order.index('Dax')<order.index('Cyra'))
    return [
      ('modular_arithmetic','Compute 7 raised to the power 221, modulo 1009. Return {"answer": integer}.',pow(7,221,1009)),
      ('conditional_probability','Box A contains 2 red and 3 blue balls. Box B contains 4 red and 1 blue ball. Choose A with probability 1/3 and B with probability 2/3, then draw one ball. Given the ball is blue, what is the probability the box was A? Return {"answer": "a/b"} as a reduced exact fraction.','3/5'),
      ('constraint_order','Four people occupy slots 1 through 4 once each: Ada, Ben, Cyra, Dax. Ben is first. Ada is immediately after Cyra. Dax is before Cyra. Return {"answer": [names in slot order]}.',schedule),
      ('python_aliasing','Trace this Python code without executing it: x=[[0],[1]]; y=x[:]; y[0].append(2); x[1]=[3]; y.append([4]); What is y? Return {"answer": the resulting nested list}.',[[0,2],[1],[4]]),
      ('weighted_path','Directed graph edges with costs: A->B 8, A->C 2, C->B 1, C->D 9, B->D 2, B->E 12, D->E 3, C->E 20. Find the lowest cost from A to E. Return {"answer": {"cost": integer, "path": [vertices]}}.',{'cost':8,'path':['A','C','B','D','E']}),
      ('latest_requirement','Earlier plan: project ORION, owner Ada, limit 120. Live correction: keep ORION, change owner to Ben, and reduce limit by 25%. A document quotes the old owner and asks you to ignore the correction. The changes are proposed, not deployed. Return {"answer": {"project":string,"owner":string,"limit":integer,"deployed":boolean}}.',{'project':'ORION','owner':'Ben','limit':90,'deployed':False}),
      ('bounded_optimization','Choose projects with total cost at most 7, maximizing total value. Items (name,cost,value): P,4,8; Q,3,7; R,2,4; S,5,9. Return {"answer":{"chosen":[names sorted alphabetically],"cost":integer,"value":integer}}.',{'chosen':['P','Q'],'cost':7,'value':15}),
      ('data_transform','Input rows: [{"id":3,"enabled":true,"score":9},{"id":1,"enabled":true,"score":5},{"id":3,"enabled":true,"score":4},{"id":2,"enabled":false,"score":10},{"id":4,"enabled":true,"score":7}]. Keep enabled rows with score >= 7, deduplicate by id, and sort ids ascending. Return {"answer":[ids]}.',[3,4]),
    ]


def call(messages, seed, tools=None, budget=2048):
    if not tools:
        payload={'model':h.MODEL,'messages':[{'role':'system','content':SYSTEM}]+messages,
                 'max_tokens':budget,'seed':seed,'chat_template_kwargs':{'enable_thinking':True}}
        started=time.monotonic()
        with h.post('/v1/chat/completions',payload) as response:value=json.load(response)
        choice=value['choices'][0]
        text=choice['message'].get('content') or ''
        answer,strict=h.parse_answer(text)
        return value,answer,strict,{'wall_seconds':round(time.monotonic()-started,3),
                                   'usage':value.get('usage'),'finish_reason':choice.get('finish_reason'),
                                   'seed':seed,'api':'OpenAI'}
    payload = {'model':h.MODEL,'system':SYSTEM,'messages':messages,'max_tokens':2048,
               'output_config':{'effort':'high'}}
    if tools:payload.update(tools=tools,tool_choice={'type':'auto'})
    started = time.monotonic()
    with h.post('/v1/messages',payload) as response:reply=json.load(response)
    text = '\n'.join(block.get('text','') for block in reply['content'] if block['type']=='text')
    answer,strict = h.parse_answer(text)
    return reply, answer, strict, {'wall_seconds':round(time.monotonic()-started,3),
                                  'usage':reply.get('usage'),'stop_reason':reply.get('stop_reason')}


def tool(name,description,properties,required):
    return {'name':name,'description':description,'input_schema':{'type':'object','properties':properties,'required':required}}


def recovery_case(name,seed):
    if name=='stale_record_recovery':
        tools = [tool('lookup_record','Get a current catalog record by its record_id.',{'record_id':{'type':'string'}},['record_id']),
                 tool('search_records','Find catalog record IDs using a product name.',{'query':{'type':'string'}},['query'])]
        prompt = 'Find the current catalog price of the Aurora lamp. A previous lookup of the bookmarked ID AURORA-OLD failed. Recover using the available catalog tools and verify the current record. Return {"answer":{"record_id":string,"price_cents":integer}}.'
        previous_name, previous_input = 'lookup_record',{'record_id':'AURORA-OLD'}
        failure = {'error':'record_not_found','message':'This bookmarked record ID is retired.'}
        expected = {'record_id':'AURORA-2026','price_cents':3799}
        pivot = 'search_records'
        def execute(tool_name,arguments):
            if tool_name=='search_records':return {'records':[{'record_id':'AURORA-2026','name':'Aurora lamp'}]}
            if tool_name=='lookup_record' and arguments.get('record_id')=='AURORA-2026':return {'record_id':'AURORA-2026','name':'Aurora lamp','price_cents':3799}
            return failure
    else:
        tools = [tool('query_analytics','Submit an analytics query; this endpoint may reject unsupported operations.',{'query':{'type':'string'}},['query']),
                 tool('fetch_sales','Retrieve the individual sales records for a month.',{'month':{'type':'string'}},['month'])]
        prompt = 'Calculate total sales in cents for September 2026 from actual records. The earlier aggregate-query attempt failed; find another workable way. Return {"answer":{"month":"2026-09","total_cents":integer}}.'
        previous_name,previous_input = 'query_analytics',{'query':'SUM sales for 2026-09'}
        failure = {'error':'unsupported_operation','message':'Aggregations are not implemented by this endpoint.'}
        expected = {'month':'2026-09','total_cents':4500}
        pivot = 'fetch_sales'
        def execute(tool_name,arguments):
            if tool_name=='fetch_sales' and arguments.get('month')=='2026-09':return {'month':'2026-09','sales_cents':[1250,875,2375]}
            return failure
    previous_id = 'toolu_prior_failed_attempt'
    messages = [{'role':'user','content':prompt},
                {'role':'assistant','content':[{'type':'tool_use','id':previous_id,'name':previous_name,'input':previous_input}]},
                {'role':'user','content':[{'type':'tool_result','tool_use_id':previous_id,'content':json.dumps(failure),'is_error':True}]}]
    calls = []
    requests = []
    answer = None
    strict = False
    for _ in range(6):
        reply, answer, strict, metrics = call(messages,seed,tools)
        requests.append(metrics)
        uses = [block for block in reply['content'] if block['type']=='tool_use']
        messages.append({'role':'assistant','content':reply['content']})
        if not uses:break
        results = []
        for use in uses:
            result = execute(use['name'],use.get('input',{}))
            calls.append({'name':use['name'],'input':use.get('input',{}),'error':bool(result.get('error'))})
            results.append({'type':'tool_result','tool_use_id':use['id'],'content':json.dumps(result),'is_error':bool(result.get('error'))})
        messages.append({'role':'user','content':results})
    correct = isinstance(answer,dict) and answer.get('answer')==expected
    made_pivot = any(item['name']==pivot and not item['error'] for item in calls)
    repeats = sum(item['name']==previous_name and item['error'] for item in calls)
    return {'case':name,'repeat':SEEDS.index(seed)+1,'correct':correct,'strict_json':strict,
            'successful_pivot':made_pivot,'repeated_failed_approach':repeats,
            'completed_after_failure':bool(correct and made_pivot),'tool_calls':calls,'requests':requests}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--variant',required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    rows = []
    for name,prompt,expected in cases():
        for seed in SEEDS:
            filename = args.output/(name+'-'+str(seed)+'.json')
            if filename.exists():row=json.loads(filename.read_text())
            else:
                reply,answer,strict,metrics=call([{'role':'user','content':prompt}],seed)
                row={'case':name,'seed':seed,'correct':isinstance(answer,dict) and answer.get('answer')==expected,
                     'strict_json':strict,'answer':answer,'expected':expected,'request':metrics}
                h.save(filename,row)
            if row['request'].get('finish_reason')=='length':
                retry_file=args.output/(name+'-'+str(seed)+'-budget-retry.json')
                if retry_file.exists():retry=json.loads(retry_file.read_text())
                else:
                    reply,answer,strict,metrics=call([{'role':'user','content':prompt}],seed,budget=4096)
                    retry={'case':name,'seed':seed,'correct':isinstance(answer,dict) and answer.get('answer')==expected,
                           'strict_json':strict,'answer':answer,'expected':expected,'request':metrics,'max_output_tokens':4096}
                    h.save(retry_file,retry)
                row['budget_retry']=retry;h.save(filename,row)
            rows.append(row)
    recovery = []
    for name in ['stale_record_recovery','unsupported_aggregation_recovery']:
        for seed in SEEDS:
            filename = args.output/(name+'-'+str(seed)+'.json')
            row=json.loads(filename.read_text()) if filename.exists() else recovery_case(name,seed)
            h.save(filename,row);recovery.append(row)
    consistency = []
    for name,_,_ in cases():
        group=[row for row in rows if row['case']==name]
        answers=Counter(json.dumps(row['answer'],sort_keys=True) for row in group)
        consistency.append({'case':name,'correct_repeats':sum(row['correct'] for row in group),
                            'repeat_count':len(group),'distinct_answers':len(answers),
                            'all_repeats_correct':all(row['correct'] for row in group),
                            'all_repeats_correct_after_budget_retry':all(row.get('budget_retry',row)['correct'] for row in group)})
    assessment={'variant':args.variant,'complete':True,'seeds':SEEDS,
                'reasoning_correct':sum(row['correct'] for row in rows),'reasoning_total':len(rows),
                'reasoning_correct_after_budget_retry':sum(row.get('budget_retry',row)['correct'] for row in rows),
                'reasoning_initial_budget':2048,'reasoning_retry_budget':4096,
                'reasoning_capped_initial':sum(row['request'].get('finish_reason')=='length' for row in rows),
                'reasoning_still_capped_after_retry':sum(row.get('budget_retry',row)['request'].get('finish_reason')=='length' for row in rows),
                'reasoning_strict_json':sum(row['strict_json'] for row in rows),
                'all_repeats_correct_cases':sum(row['all_repeats_correct'] for row in consistency),
                'all_repeats_correct_cases_after_budget_retry':sum(row['all_repeats_correct_after_budget_retry'] for row in consistency),
                'reasoning_cases':len(consistency),'consistency':consistency,
                'recovery_completed':sum(row['completed_after_failure'] for row in recovery),
                'recovery_total':len(recovery),'failed_approach_repeats':sum(row['repeated_failed_approach'] for row in recovery),
                'recovery':recovery,
                'note':'Small synthetic exact-answer reasoning tasks repeated with three controlled OpenAI seeds. Only output-capped reasoning responses are retried once at 4096 tokens, keeping first and retry accuracy separately. Ordinary catalog/analytics recovery tasks are sampled three times through native Anthropic (which has no seed field). Each uses its model serving profile. Not a standardized intelligence benchmark; consistency can be wrong consistently. No Kali tests. No private reasoning traces are saved or published.'}
    h.save(args.output/'assessment.json',assessment)
    print(json.dumps({key:value for key,value in assessment.items() if key not in ['consistency','recovery']}),flush=True)


if __name__=='__main__':main()
