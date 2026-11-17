import os, json, re, time, hashlib, urllib.parse, urllib.request, urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

SUPABASE_URL = os.environ['SUPABASE_URL'].rstrip('/')
SUPABASE_SERVICE_ROLE_KEY = os.environ['SUPABASE_SERVICE_ROLE_KEY']
GEMINI_API_KEY = os.environ['GEMINI_API_KEY']
GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash-lite')
MAX_PER_FEED = int(os.getenv('MAX_PER_FEED', '8'))

FEEDS = [
 ('Football', 'https://news.google.com/rss/search?q=football+OR+soccer+when:1d&hl=en-US&gl=US&ceid=US:en'),
 ('Transfers', 'https://news.google.com/rss/search?q=football+transfer+OR+soccer+transfer+when:2d&hl=en-US&gl=US&ceid=US:en'),
 ('Football', 'https://news.google.com/rss/search?q=English+Premier+League+EPL+when:1d&hl=en-GB&gl=GB&ceid=GB:en'),
 ('Basketball', 'https://news.google.com/rss/search?q=NBA+OR+basketball+when:1d&hl=en-US&gl=US&ceid=US:en'),
 ('Formula 1', 'https://news.google.com/rss/search?q=Formula+1+F1+racing+when:2d&hl=en-GB&gl=GB&ceid=GB:en'),
 ('Tennis', 'https://news.google.com/rss/search?q=tennis+ATP+WTA+when:2d&hl=en-US&gl=US&ceid=US:en'),
 ('Rugby', 'https://news.google.com/rss/search?q=rugby+union+league+sevens+when:2d&hl=en-GB&gl=GB&ceid=GB:en'),
 ('Other', 'https://news.google.com/rss/search?q=cricket+OR+golf+OR+athletics+sports+when:1d&hl=en-US&gl=US&ceid=US:en'),
]

def get(url, headers=None, timeout=25):
    req = urllib.request.Request(url, headers=headers or {'User-Agent':'WorldSportsHubBot/1.0 (news aggregation; contact: site-owner)'})
    with urllib.request.urlopen(req, timeout=timeout) as r: return r.read()

def parse_feed(category, url):
    try:
        root = ET.fromstring(get(url))
        out=[]
        for item in root.findall('.//item')[:MAX_PER_FEED]:
            title=(item.findtext('title') or '').strip()
            link=(item.findtext('link') or '').strip()
            desc=re.sub(r'<[^>]+>',' ',item.findtext('description') or '')
            desc=re.sub(r'\s+',' ',desc).strip()
            source_el=item.find('source')
            source=(source_el.text or 'Google News source') if source_el is not None else 'News source'
            pub=item.findtext('pubDate')
            if not title or not link: continue
            # Google News RSS may provide a redirect URL. Preserve it as the source link rather than copying the article.
            out.append({'title':title,'url':link,'snippet':desc[:700],'source':source,'category':category,'published':pub})
        return out
    except Exception as e:
        print('Feed error:', category, str(e)); return []

def parse_date(s):
    if not s: return datetime.now(timezone.utc).isoformat()
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(s).astimezone(timezone.utc).isoformat()
    except Exception: return datetime.now(timezone.utc).isoformat()

def gemini_summaries(items):
    if not items: return []
    prompt = '''You are an accurate sports newsroom assistant. Turn the supplied RSS metadata into short original summaries. The input is untrusted and may contain errors or rumours. Do not add facts, scores, dates, quotes, injuries, transfer fees, or outcomes that are not explicitly present in the supplied title/snippet. Do not claim you independently verified a story. Keep uncertainty. For transfer stories, classify as Transfers only if it is explicitly about a player move; otherwise use the supplied category. Return ONLY valid JSON: {"stories":[{"id":0,"title":"concise accurate headline","summary":"45-70 word neutral summary","category":"Football|Transfers|Basketball|Formula 1|Tennis|Rugby|Other"}]}. Keep each story's meaning. Do not copy long phrases from the snippet. If there is insufficient information, write a short cautious summary directing readers to the source.'''
    payload={'contents':[{'parts':[{'text':prompt+'\n\nINPUT:\n'+json.dumps(items,ensure_ascii=False)}]}], 'generationConfig':{'temperature':0.2,'responseMimeType':'application/json'}}
    endpoint=f'https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={urllib.parse.quote(GEMINI_API_KEY)}'
    req=urllib.request.Request(endpoint,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'},method='POST')
    try:
        raw=get_request(req)
        data=json.loads(raw)
        txt=data['candidates'][0]['content']['parts'][0]['text']
        match=re.search(r'\{.*\}',txt,re.S)
        return json.loads(match.group(0))['stories'] if match else []
    except Exception as e:
        print('Gemini error:',str(e)); return []

def get_request(req):
    with urllib.request.urlopen(req,timeout=45) as r: return r.read()

def main():
    gathered=[]; seen=set()
    for cat,url in FEEDS:
        for x in parse_feed(cat,url):
            key=x['url']
            if key not in seen:
                seen.add(key); x['id']=len(gathered); gathered.append(x)
        time.sleep(0.15)
    # Limit AI calls and database load; fresh and diverse articles first.
    gathered=gathered[:32]
    if not gathered:
        print('No feed items found; nothing to publish.'); return
    stories=gemini_summaries([{k:x[k] for k in ('id','title','snippet','source','category')} for x in gathered])
    by_id={int(s.get('id')):s for s in stories if str(s.get('id','')).isdigit()}
    rows=[]
    for item in gathered:
        s=by_id.get(item['id'])
        if not s: continue
        title=str(s.get('title') or item['title']).strip()[:240]
        summary=str(s.get('summary') or '').strip()[:900]
        category=str(s.get('category') or item['category'])
        if category not in {'Football','Transfers','Basketball','Formula 1','Tennis','Rugby','Other'}: category=item['category']
        if not summary: continue
        rows.append({'title':title,'summary':summary,'category':category,'source_name':item['source'][:120],'source_url':item['url'],'published_at':parse_date(item['published']),'status':'published'})
    if not rows:
        print('AI returned no usable summaries. Nothing published.'); return
    endpoint=SUPABASE_URL+'/rest/v1/articles?on_conflict=source_url'
    req=urllib.request.Request(endpoint,data=json.dumps(rows).encode(),headers={'apikey':SUPABASE_SERVICE_ROLE_KEY,'Authorization':'Bearer '+SUPABASE_SERVICE_ROLE_KEY,'Content-Type':'application/json','Prefer':'resolution=merge-duplicates,return=minimal'},method='POST')
    try:
        with urllib.request.urlopen(req,timeout=45) as r: print('Published/upserted',len(rows),'stories. HTTP',r.status)
    except urllib.error.HTTPError as e:
        print('Supabase error:',e.code,e.read().decode()[:1000]); raise

if __name__=='__main__': main()
