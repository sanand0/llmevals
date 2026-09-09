#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["openai>=1.0"]
# ///
"""Screen confidence-elicitation prompts on 2 BANKING77 cases per intent, resumably."""
from __future__ import annotations
import asyncio, csv, json, random, re
from openai import AsyncOpenAI
from common import DATA, openai_api_key
from prompt_fragments import SCREEN_VARIANTS

MODEL='gpt-5.6-luna'
INPUT=DATA/'banking77-sample.csv'
OUT=DATA/'prompt-screen-results.csv'
FIELDS=['variant','model','id','gold','prediction','confidence','correct','raw']
VARIANTS=SCREEN_VARIANTS

def parse_json(text):
    return json.loads(re.sub(r'^```(?:json)?\s*|\s*```$','',text.strip(),flags=re.I))

def append(row):
    new=not OUT.exists()
    with OUT.open('a',newline='') as f:
        w=csv.DictWriter(f,fieldnames=FIELDS)
        if new:w.writeheader()
        w.writerow(row)

def done():
    return {(r['variant'],r['id']) for r in csv.DictReader(OUT.open())} if OUT.exists() else set()

def screen_rows(rows):
    by={}
    for r in rows: by.setdefault(r['category'],[]).append(r)
    return [r for label in sorted(by) for r in sorted(by[label],key=lambda x:x['id'])[:2]]

async def main(concurrency=24):
    all_rows=list(csv.DictReader(INPUT.open())); rows=screen_rows(all_rows)
    assert len(rows)==154
    labels=sorted({r['category'] for r in all_rows})
    allowed=json.dumps(labels,separators=(',',':'))
    seen=done(); jobs=[(v,r) for v in VARIANTS for r in rows if (v,r['id']) not in seen]
    random.Random(42).shuffle(jobs)
    print(f'{len(jobs)} pending / {len(VARIANTS)*len(rows)} total',flush=True)
    if not jobs:
        return
    client=AsyncOpenAI(api_key=openai_api_key()); sem=asyncio.Semaphore(concurrency)
    async def one(v,r):
        prompt=f'''Classify this customer request into exactly one of the allowed labels below.\n\nAllowed labels:\n{allowed}\n\nRequest:\n{r["text"]}\n\nConfidence instruction:\n{VARIANTS[v]}\n\nReturn ONLY JSON with label (exactly one allowed label) and confidence (integer 0-100).'''
        async with sem:
            last=None
            for attempt in range(5):
                try:
                    out=await client.responses.create(model=MODEL,input=prompt,max_output_tokens=80,reasoning={'effort':'none'})
                    raw=out.output_text.strip(); obj=parse_json(raw); pred=str(obj['label']); conf=int(round(float(obj['confidence'])))
                    if not 0<=conf<=100: raise ValueError('confidence out of range')
                    return {'variant':v,'model':MODEL,'id':r['id'],'gold':r['category'],'prediction':pred,'confidence':conf,'correct':int(pred==r['category']),'raw':raw.replace('\n',' ')}
                except Exception as e:
                    last=e; await asyncio.sleep(min(8,.5*2**attempt))
            raise RuntimeError(f'{v}/{r["id"]}: {last}')
    n=0
    for fut in asyncio.as_completed([one(v,r) for v,r in jobs]):
        append(await fut); n+=1
        if n%100==0 or n==len(jobs): print(f'completed {n}/{len(jobs)}',flush=True)

if __name__=='__main__': asyncio.run(main())
