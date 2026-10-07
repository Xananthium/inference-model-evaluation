"""Portable HTTP and grading helpers; credentials come only from the environment."""
import json
import os
import re
import urllib.request

MODEL=os.environ.get('MODEL','qwen3.6-35b-hauhau-w4a16-vision')
API_BASE_URL=os.environ.get('API_BASE_URL','http://127.0.0.1:8000').rstrip('/')


def post(path,payload):
    headers={'Content-Type':'application/json','anthropic-version':'2023-06-01'}
    key=os.environ.get('API_KEY')
    if key:headers.update({'x-api-key':key,'Authorization':'Bearer '+key})
    request=urllib.request.Request(API_BASE_URL+path,data=json.dumps(payload).encode(),headers=headers)
    return urllib.request.urlopen(request,timeout=900)


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,indent=2));temporary.replace(path)


def parse_answer(text):
    try:return json.loads(text.strip()),True
    except ValueError:
        cleaned=re.sub(r'^```(?:json)?\s*|\s*```$','',text.strip())
        try:return json.loads(cleaned),False
        except ValueError:
            decoder=json.JSONDecoder()
            for match in re.finditer(r'\{',text):
                try:
                    obj,_=decoder.raw_decode(text[match.start():]);return obj,False
                except ValueError:pass
            return None,False
