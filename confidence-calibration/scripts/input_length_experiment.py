#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["openai>=1.0"]
# ///
"""Paired BANKING77 stress test with 0/500/2,000 irrelevant context words."""
from __future__ import annotations
import argparse, asyncio, csv, json, random, re
from openai import AsyncOpenAI
from common import DATA, openai_api_key
from prompt_fragments import BASELINE

OUT=DATA/'input-length-results.csv'
FIELDS=['model','condition','id','gold','prediction','confidence','correct','request_words','padding_words','raw']
SEED=20260909
FACTS=[
    'Profile locale is en-GB and the interface language is English.',
    'The account interface uses dark appearance and a medium text size.',
    'The device operating system was updated recently and reports normal health.',
    'The session timezone is Europe/London and the clock is synchronized.',
    'The customer has enabled email notifications but disabled promotional messages.',
    'The browser viewport is 1440 by 900 pixels with standard zoom.',
    'The connection type is Wi-Fi and the latency check completed normally.',
    'The customer opened the help centre before starting this conversation.',
    'The profile was created several years ago and the display name is unchanged.',
    'Accessibility settings use default contrast and no screen reader was detected.',
    'The application build is from the current stable release channel.',
    'Telemetry shows the session started normally without a crash or restart.',
    'The preferred date format is day-month-year and the number format uses commas.',
    'The user has not changed notification preferences during this session.',
    'A satisfaction survey from a previous visit was completed without free-text comments.',
    'The device battery level is above half and power-saving mode is disabled.',
    'The current session has one active window and no background upload is running.',
    'The user profile includes a preferred first name but no pronunciation guide.',
    'The help-centre theme follows the operating-system appearance setting.',
    'The last successful sign-in used the same general device family as today.',
]

def words(s): return len(re.findall(r'\b\w+\b',s))

def padding_for(row,target):
    if target==0: return ''
    rng=random.Random(f'{SEED}:{row["id"]}:{target}'); pieces=[]
    while words(' '.join(pieces))<target:
        batch=FACTS[:]; rng.shuffle(batch); pieces.extend(batch)
    return ' '.join(re.findall(r'\S+',' '.join(pieces))[:target])

def done():
    return {(r['model'],r['condition'],r['id']) for r in csv.DictReader(OUT.open())} if OUT.exists() else set()

def append(row):
    new=not OUT.exists()
    with OUT.open('a',newline='') as f:
        w=csv.DictWriter(f,fieldnames=FIELDS)
        if new:w.writeheader()
        w.writerow(row)

def parse_json(text):
    return json.loads(re.sub(r'^```(?:json)?\s*|\s*```$','',text.strip(),flags=re.I))

async def run(model,condition,padding_words,concurrency):
    rows=list(csv.DictReader((DATA/'banking77-sample.csv').open()))
    labels=sorted({r['category'] for r in rows}); allowed=json.dumps(labels,separators=(',',':'))
    completed=done(); pending=[r for r in rows if (model,condition,r['id']) not in completed]
    random.Random(SEED).shuffle(pending)
    print(f'{model} {condition}: {len(pending)} pending / {len(rows)}',flush=True)
    if not pending:
        return
    client=AsyncOpenAI(api_key=openai_api_key()); sem=asyncio.Semaphore(concurrency)
    async def one(r):
        pad=padding_for(r,padding_words)
        background=(f'\n\nBACKGROUND METADATA (not necessarily relevant):\n{pad}' if pad else '')
        prompt=f'''Classify the CURRENT REQUEST into exactly one of the allowed labels below. Background metadata, if present, is incidental context and should only affect the answer if genuinely relevant.\n\nAllowed labels:\n{allowed}{background}\n\nCURRENT REQUEST:\n{r["text"]}\n\nReturn ONLY JSON with label (exactly one allowed label) and confidence (integer 0-100): {BASELINE}'''
        async with sem:
            last=None
            for attempt in range(5):
                try:
                    kw={'model':model,'input':prompt,'max_output_tokens':80}
                    if model=='gpt-5.6-luna':kw['reasoning']={'effort':'none'}
                    else:kw['temperature']=0
                    resp=await client.responses.create(**kw)
                    raw=resp.output_text.strip(); obj=parse_json(raw); conf=int(round(float(obj['confidence']))); pred=str(obj['label'])
                    if not 0<=conf<=100:raise ValueError('confidence out of range')
                    return {'model':model,'condition':condition,'id':r['id'],'gold':r['category'],'prediction':pred,'confidence':conf,'correct':int(pred==r['category']),'request_words':words(r['text']),'padding_words':padding_words,'raw':raw.replace('\n',' ')}
                except Exception as e:
                    last=e; await asyncio.sleep(min(8,.5*2**attempt))
            raise RuntimeError(f'{r["id"]} failed: {last}')
    n=0
    for fut in asyncio.as_completed([one(r) for r in pending]):
        append(await fut); n+=1
        if n%100==0 or n==len(pending):print(f'  completed {n}/{len(pending)}',flush=True)

def main():
    p=argparse.ArgumentParser();p.add_argument('--model',required=True);p.add_argument('--condition',choices=['short','medium','long'],required=True);p.add_argument('--concurrency',type=int,default=30);a=p.parse_args()
    asyncio.run(run(a.model,a.condition,{'short':0,'medium':500,'long':2000}[a.condition],a.concurrency))
if __name__=='__main__':main()
