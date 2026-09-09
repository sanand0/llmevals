#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["openai>=1.0"]
# ///
"""Run the BANKING77 confidence-calibration benchmark, resumably."""
from __future__ import annotations
import argparse, asyncio, csv, json, random, re
from openai import AsyncOpenAI
from common import DATA, openai_api_key
from prompt_fragments import BASELINE

RESULTS=DATA/'results.csv'
FIELDS=['task','model','id','gold','prediction','confidence','correct','raw']

def parse_json(text):
    text=re.sub(r'^```(?:json)?\s*|\s*```$', '', text.strip(), flags=re.I)
    return json.loads(text)

def done_keys():
    if not RESULTS.exists(): return set()
    return {(r['task'],r['model'],r['id']) for r in csv.DictReader(RESULTS.open())}

def append(row):
    new=not RESULTS.exists()
    with RESULTS.open('a', newline='') as f:
        w=csv.DictWriter(f, fieldnames=FIELDS)
        if new: w.writeheader()
        w.writerow(row)

async def run(model, concurrency):
    task='banking77'
    rows=list(csv.DictReader((DATA/'banking77-sample.csv').open()))
    labels=sorted({r['category'] for r in rows})
    allowed=json.dumps(labels,separators=(',',':'))
    def prompt(r): return f'''Classify this customer request into exactly one of the allowed labels below.\n\nAllowed labels:\n{allowed}\n\nRequest:\n{r["text"]}\n\nReturn ONLY JSON with label (exactly one allowed label) and confidence (integer 0-100): {BASELINE}'''
    pending=[r for r in rows if (task,model,r['id']) not in done_keys()]
    random.Random(42).shuffle(pending)
    print(f'{task} {model}: {len(pending)} pending / {len(rows)} total', flush=True)
    if not pending:
        return
    client=AsyncOpenAI(api_key=openai_api_key())
    sem=asyncio.Semaphore(concurrency)
    async def one(r):
        async with sem:
            last=None
            for attempt in range(5):
                try:
                    kw={'model':model,'input':prompt(r),'max_output_tokens':80}
                    if model=='gpt-5.6-luna': kw['reasoning']={'effort':'none'}
                    else: kw['temperature']=0
                    response=await client.responses.create(**kw)
                    raw=response.output_text.strip(); obj=parse_json(raw)
                    confidence=int(round(float(obj['confidence'])))
                    if not 0<=confidence<=100: raise ValueError('confidence out of range')
                    prediction=str(obj['label'])
                    return {'task':task,'model':model,'id':r['id'],'gold':r['category'],'prediction':prediction,'confidence':confidence,'correct':int(prediction==r['category']),'raw':raw.replace('\n',' ')}
                except Exception as e:
                    last=e; await asyncio.sleep(min(8,.5*2**attempt))
            raise RuntimeError(f'{r["id"]} failed: {last}')
    n=0
    for future in asyncio.as_completed([one(r) for r in pending]):
        append(await future); n+=1
        if n%25==0 or n==len(pending): print(f'  completed {n}/{len(pending)}', flush=True)

def main():
    p=argparse.ArgumentParser(); p.add_argument('--model',required=True); p.add_argument('--task',default='banking77',choices=['banking77']); p.add_argument('--concurrency',type=int,default=20); a=p.parse_args()
    asyncio.run(run(a.model,a.concurrency))
if __name__=='__main__': main()
