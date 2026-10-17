#!/usr/bin/env python3
"""Daily EOD stock snapshot: Yahoo Finance unofficial data, explicit quality/lag flags."""
import json, os, time, datetime, pathlib, sys
from zoneinfo import ZoneInfo
from urllib.request import urlopen, Request
ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/'data'/'market.json'
WATCH_FILE=ROOT/'data'/'watchlist.json'
def load_watch():
    raw=json.loads(WATCH_FILE.read_text(encoding='utf8'))
    rows=raw.get('stocks',[])
    if raw.get('schema')!='zhu-watch-v42' or len(rows)!=24 or len({v.get('id') for v in rows})!=24:
        raise ValueError('Official watchlist must contain 24 unique symbols')
    return [(v['id'],v['name'],v['type']) for v in rows]
WATCH=load_watch()

def fetch(ticker):
    from urllib.parse import quote
    last=None
    for suffix in ('.TW','.TWO'):
        symbol=ticker+suffix
        url=f'https://query1.finance.yahoo.com/v8/finance/chart/{quote(symbol)}?range=1y&interval=1d&events=div%2Csplits'
        try:
            req=Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; ZhuResearchDashboard/1.0)','Accept':'application/json'})
            with urlopen(req,timeout=22) as r: data=json.load(r)
            err=data['chart'].get('error'); result=data['chart']['result']
            if err or not result: raise ValueError(str(err))
            obj=result[0]; quote_data=obj['indicators']['quote'][0]; stamp=obj.get('timestamp') or []
            tz=obj.get('meta',{}).get('exchangeTimezoneName','Asia/Taipei')
            rows=[]
            for i,t in enumerate(stamp):
                vals={k:quote_data.get(k,[None]*len(stamp))[i] for k in ('open','high','low','close','volume')}
                if any(vals[k] is None for k in ('open','high','low','close')):continue
                if vals['volume'] is None:continue
                if vals['high'] < vals['low'] or vals['close']<=0:continue
                d=datetime.datetime.fromtimestamp(t,ZoneInfo(tz)).date().isoformat()
                rows.append({'date':d, **{k:round(float(v),4) if k!='volume' else int(v) for k,v in vals.items()}})
            uniq={r['date']:r for r in rows}
            rows=sorted(uniq.values(),key=lambda x:x['date'])[-260:]
            if len(rows)<45:raise ValueError(f'insufficient bars {len(rows)}')
            return {'symbol':symbol,'bars':rows,'currency':obj.get('meta',{}).get('currency','TWD')}
        except Exception as e:last=str(e)
    raise RuntimeError(last or 'unavailable')
def main():
    existing={}
    if OUT.exists():
        try:existing=json.loads(OUT.read_text(encoding='utf8')).get('symbols',{})
        except Exception:pass
    now=datetime.datetime.now(ZoneInfo('Asia/Taipei'))
    symbols={};errors={}
    for ticker,name,kind in WATCH:
        try:
            data=fetch(ticker);symbols[ticker]=data
            print(ticker,data['symbol'],data['bars'][-1]['date'],flush=True)
        except Exception as e:
            errors[ticker]=str(e)
            if ticker in existing: symbols[ticker]={**existing[ticker],'carryForward':True}
            print('WARN',ticker,e,file=sys.stderr,flush=True)
        time.sleep(.3)
    if not symbols:raise SystemExit('No new or cached data; refusing to write empty dataset')
    payload={'schema':'zhu-market-v4','generatedAt':now.isoformat(),'timezone':'Asia/Taipei','source':'Yahoo Finance chart endpoint (unofficial; may be delayed/inaccurate; not adjusted for corporate actions)','symbols':symbols,'errors':errors,'note':'Daily OHLCV only. Missing or stale symbols are never confirmed formal buy signals.'}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    tmp=OUT.with_suffix('.tmp');tmp.write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':')),encoding='utf8');tmp.replace(OUT)
    print('wrote',OUT, 'success',len(symbols),'errors',len(errors))
if __name__=='__main__':main()
