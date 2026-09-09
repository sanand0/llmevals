#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["openai>=1.0"]
# ///
"""Compare confidence-request wordings on the same BANKING77 cases, resumably."""
from __future__ import annotations
import asyncio, csv, json, random, re
from openai import AsyncOpenAI
from common import DATA, openai_api_key
from prompt_fragments import FULL_VARIANTS

MODEL='gpt-5.6-luna'
INPUT=DATA/'banking77-sample.csv'
OUT=DATA/'prompt-variant-results.csv'
FIELDS=['variant','model','id','gold','prediction','confidence','correct','raw']
VARIANTS=FULL_VARIANTS

def parse_json(text):
    return json.loads(re.sub(r'^```(?:json)?\s*|\s*```$','',text.strip(),flags=re.I))

def existing():
    return {(r['variant'],r['id']) for r in csv.DictReader(OUT.open())} if OUT.exists() else set()

def append(row):
    new=not OUT.exists()
    with OUT.open('a',newline='') as f:
        w=csv.DictWriter(f,fieldnames=FIELDS)
        if new:w.writeheader()
        w.writerow(row)

def seed_from_screen():
    """Reuse promoted top-two rows because the prompt fragment is identical."""
    screen=DATA/'prompt-screen-results.csv'
    if not screen.exists(): return 0
    seen=existing(); added=0
    for row in csv.DictReader(screen.open()):
        if row['variant']=='top_two_mass' and (row['variant'],row['id']) not in seen:
            append(row); seen.add((row['variant'],row['id'])); added+=1
    if added: print(f'seeded {added} top_two_mass rows from prompt screen',flush=True)
    return added

async def main(concurrency=24):
    seed_from_screen()
    rows=list(csv.DictReader(INPUT.open()))
    if len(rows)!=770: raise SystemExit(f'Expected 770 BANKING77 rows, found {len(rows)}')
    labels=sorted({r['category'] for r in rows}); allowed=json.dumps(labels,separators=(',',':'))
    done=existing(); jobs=[(v,r) for v in VARIANTS for r in rows if (v,r['id']) not in done]
    random.Random(42).shuffle(jobs)
    print(f'{len(jobs)} pending / {len(VARIANTS)*len(rows)} total',flush=True)
    if not jobs:
        return
    client=AsyncOpenAI(api_key=openai_api_key()); sem=asyncio.Semaphore(concurrency)
    async def one(variant,r):
        prompt=f'''Classify this customer request into exactly one of the allowed labels below.\n\nAllowed labels:\n{allowed}\n\nRequest:\n{r["text"]}\n\nConfidence instruction:\n{VARIANTS[variant]}\n\nReturn ONLY JSON with label (exactly one allowed label) and confidence (integer 0-100).'''
        async with sem:
            last=None
            for attempt in range(5):
                try:
                    response=await client.responses.create(model=MODEL,input=prompt,max_output_tokens=80,reasoning={'effort':'none'})
                    raw=response.output_text.strip(); obj=parse_json(raw); pred=str(obj['label']); conf=int(round(float(obj['confidence'])))
                    if not 0<=conf<=100: raise ValueError('confidence out of range')
                    return {'variant':variant,'model':MODEL,'id':r['id'],'gold':r['category'],'prediction':pred,'confidence':conf,'correct':int(pred==r['category']),'raw':raw.replace('\n',' ')}
                except Exception as e:
                    last=e; await asyncio.sleep(min(8,.5*2**attempt))
            raise RuntimeError(f'{variant}/{r["id"]} failed: {last}')
    n=0
    for fut in asyncio.as_completed([one(v,r) for v,r in jobs]):
        append(await fut); n+=1
        if n%100==0 or n==len(jobs): print(f'completed {n}/{len(jobs)}',flush=True)

if __name__=='__main__': asyncio.run(main())
