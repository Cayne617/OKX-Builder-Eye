"""
OKX Builder Eye v5.0 — Vercel Edition
KOL 发现 → 拓展 → 运营 → 转化 全链路闭环
"""
import os, json, math, io
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Query, UploadFile, File, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import httpx
import pandas as pd
from sqlalchemy import create_engine, text, Column, Integer, String, Float, Boolean, Text, DateTime, JSON
from sqlalchemy.orm import declarative_base, sessionmaker

# ===== CONFIG =====
DATABASE_URL = os.getenv("POSTGRES_URL", os.getenv("DATABASE_URL", ""))
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
FEISHU_WEBHOOK = os.getenv("FEISHU_WEBHOOK", "")

OFFICIAL = {"mercy_okx","misaenfp","mia_okx","star_okx","haiteng_okx","okxchinese","okxwallet_cn","okx_yuki"}

PRODUCT_KW = {
    "Onchain OS":["onchain os","onchain"],"OKX Wallet":["okx钱包","okx wallet","欧易钱包","web3钱包"],
    "Trade Kit":["trade kit"],"OpenClaw":["openclaw","claw","龙虾"],"OKB":["okb","$okb"],
    "Agentic Wallet":["agentic wallet","agentic"],"OKX赚币":["赚币","earn"],
    "Orbit":["orbit","星球"],"OKX合约":["合约交易","网格交易"],
}

TAG_KW = {
    "撸毛":["撸毛","空投","airdrop"],"AI":["ai agent","AI","大模型","deepseek","openclaw","agent"],
    "DEX":["dex","uniswap","swap","闪兑"],"Meme":["meme","pepe","doge","pump"],
    "DeFi":["defi","yield","质押","stake","借贷"],"链上":["链上","onchain","钱包","wallet"],
    "交易":["交易","trade","合约","多空","杠杆","网格"],"市场":["btc","eth","行情","牛市","熊市","宏观"],
    "教程":["教程","教学","入门","科普"],"安全":["安全","被盗","黑客","漏洞","诈骗"],
}

# ===== DATABASE =====
Base = declarative_base()

class KOL(Base):
    __tablename__ = "kols"
    id = Column(Integer, primary_key=True)
    handle = Column(String(100), unique=True, index=True)
    nickname = Column(String(200), default="")
    bd = Column(String(100), default="")
    tier = Column(String(5), default="")
    cost = Column(Float, default=0)
    avg_price = Column(Float, default=0)
    followers = Column(Integer, default=0)
    okx_tweets = Column(Integer, default=0)
    okx_impressions = Column(Integer, default=0)
    bn_tweets = Column(Integer, default=0)
    bn_impressions = Column(Integer, default=0)
    total_tweets = Column(Integer, default=0)
    total_impressions = Column(Integer, default=0)
    okx_pos = Column(Integer, default=0)
    okx_neg = Column(Integer, default=0)
    okx_neu = Column(Integer, default=0)
    tags = Column(JSON, default=list)
    products = Column(JSON, default=list)
    score = Column(Float, default=0)
    is_partner = Column(Boolean, default=False)
    is_official = Column(Boolean, default=False)
    orbit_status = Column(String(20), default="none")
    wallet_address = Column(String(200), default="")
    okx_uid = Column(String(100), default="")
    week_date = Column(String(10), default="")
    updated_at = Column(DateTime, default=datetime.utcnow)

class Post(Base):
    __tablename__ = "posts"
    id = Column(Integer, primary_key=True)
    handle = Column(String(100), index=True)
    link = Column(String(500), default="")
    description = Column(Text, default="")
    impressions = Column(Integer, default=0)
    likes = Column(Integer, default=0)
    comments = Column(Integer, default=0)
    sentiment = Column(Integer, default=0)
    mentions = Column(JSON, default=list)
    products_mentioned = Column(JSON, default=list)
    published_at = Column(String(20), default="")
    week_date = Column(String(10), default="")

# Engine + Session
engine = create_engine(DATABASE_URL, pool_pre_ping=True) if DATABASE_URL else None
SessionLocal = sessionmaker(bind=engine) if engine else None

def get_db():
    if not SessionLocal:
        return None
    db = SessionLocal()
    try:
        return db
    except:
        db.close()
        return None

def init_db():
    if engine:
        Base.metadata.create_all(engine)

# ===== SCORING =====
def calc_score(k):
    ot = k.okx_tweets or 0
    oi = k.okx_impressions or 0
    bt = k.bn_tweets or 0
    prods = k.products or []
    tS = 100 if ot>=8 else (60 if ot>=4 else (30 if ot>=1 else 0))
    iS = min(100, math.log10(max(oi,1))*20) if oi>0 else 0
    pS = 80 if len(prods)>=2 else (50 if prods else 20)
    bnP = max(0, 100-bt/ot*30) if bt>0 and ot>0 else (20 if bt>0 else 80)
    return round(tS*.2 + iS*.2 + pS*.15 + bnP*.15 + 50*.3)

# ===== CRM PARSER =====
def parse_and_import(crm_bytes: bytes, gsheet_bytes: bytes = None):
    """Parse CRM Excel + optional GSheet, import to database."""
    db = get_db()
    if not db:
        return {"error": "Database not connected"}

    crm_df1 = pd.read_excel(io.BytesIO(crm_bytes), sheet_name=0)
    crm_df2 = pd.read_excel(io.BytesIO(crm_bytes), sheet_name=1)

    # GSheet partner list
    gsheet_map = {}
    if gsheet_bytes:
        gdf = pd.read_excel(io.BytesIO(gsheet_bytes))
        for _, r in gdf.iterrows():
            h = str(r.get('推特ID','')).strip().replace('@','')
            if not h: continue
            gsheet_map[h.lower()] = {
                'nick': str(r.get('推特昵称','')) if pd.notna(r.get('推特昵称')) else '',
                'tier': str(r.get('层级','')) if pd.notna(r.get('层级')) else '',
                'cost': float(r.get('总费用(USDT)',0)) if pd.notna(r.get('总费用(USDT)')) else 0,
                'avg_price': float(r.get('单条均价',0)) if pd.notna(r.get('单条均价')) else 0,
                'followers': int(r.get('粉丝数',0)) if pd.notna(r.get('粉丝数')) else 0,
                'wallet': str(r.get('钱包地址','')) if pd.notna(r.get('钱包地址')) else '',
            }

    # Parse Sheet1: BD-KOL aggregation
    kol_map = {}
    week_date = str(crm_df1.iloc[0].get('pt','')) if len(crm_df1)>0 else ''
    for _, row in crm_df1.iterrows():
        h = str(row['social_media_user_name'])
        if h.lower() in OFFICIAL: continue
        bd = str(row['owner_name'])
        m = str(row['mention_text'])
        t, imp = int(row['tweet_count']), int(row['impression_count'])
        pos, neg, neu = int(row['sentiment_positive_count']), int(row['sentiment_negative_count']), int(row['sentiment_neutral_count'])
        if h not in kol_map:
            kol_map[h] = {'bd':bd,'ot':0,'oi':0,'bt':0,'bi':0,'tt':0,'ti':0,'op':0,'on':0,'ou':0}
        k = kol_map[h]
        k['tt']+=t; k['ti']+=imp
        if m=='okx': k['ot']+=t; k['oi']+=imp; k['op']+=pos; k['on']+=neg; k['ou']+=neu
        elif m=='binance': k['bt']+=t; k['bi']+=imp

    # Parse Sheet2: Posts + tags + products
    kol_texts = {}
    posts_data = []
    for _, row in crm_df2.iterrows():
        h = str(row['social_media_user_name'])
        if h.lower() in OFFICIAL: continue
        desc = str(row.get('post_description',''))[:1000] if pd.notna(row.get('post_description')) else ''
        mentions_raw = str(row.get('mention_texts',''))
        kol_texts.setdefault(h, []).append(desc[:500])
        prods = []
        if 'okx' in mentions_raw.lower():
            dl = desc.lower()
            for pn, kws in PRODUCT_KW.items():
                if any(kw in dl for kw in kws): prods.append(pn)
        posts_data.append({
            'handle':h, 'link':str(row.get('post_link','')),
            'description':desc, 'impressions':int(row.get('impression_count',0)) if pd.notna(row.get('impression_count')) else 0,
            'likes':int(row.get('like_count',0)) if pd.notna(row.get('like_count')) else 0,
            'comments':int(row.get('comment_count',0)) if pd.notna(row.get('comment_count')) else 0,
            'sentiment':int(row.get('sentiment',0)) if pd.notna(row.get('sentiment')) else 0,
            'mentions': mentions_raw, 'products_mentioned': prods,
            'published_at': str(row.get('published_at',''))[:19] if pd.notna(row.get('published_at')) else '',
            'week_date': week_date,
        })

    # Auto-tag
    kol_tags = {}
    for h, texts in kol_texts.items():
        all_text = ' '.join(texts).lower()
        tags = [tag for tag, kws in TAG_KW.items() if any(kw.lower() in all_text for kw in kws)]
        kol_tags[h] = tags or ['综合']

    # Product associations
    kol_prods = {}
    for p in posts_data:
        if p['products_mentioned']:
            kol_prods.setdefault(p['handle'], set()).update(p['products_mentioned'])

    # Clear old data and import
    db.execute(text("DELETE FROM posts"))
    db.execute(text("DELETE FROM kols"))

    imported_handles = set()
    for h, info in kol_map.items():
        gs = gsheet_map.get(h.lower(), {})
        kol = KOL(
            handle=h, nickname=gs.get('nick',''), bd=info['bd'],
            tier=gs.get('tier',''), cost=gs.get('cost',0), avg_price=gs.get('avg_price',0),
            followers=gs.get('followers',0),
            okx_tweets=info['ot'], okx_impressions=info['oi'],
            bn_tweets=info['bt'], bn_impressions=info['bi'],
            total_tweets=info['tt'], total_impressions=info['ti'],
            okx_pos=info['op'], okx_neg=info['on'], okx_neu=info['ou'],
            tags=kol_tags.get(h, ['综合']),
            products=list(kol_prods.get(h, [])),
            is_partner=h.lower() in gsheet_map,
            is_official=False,
            wallet_address=gs.get('wallet',''),
            week_date=week_date,
        )
        kol.score = calc_score(kol)
        db.add(kol)
        imported_handles.add(h.lower())

    # Also import GSheet KOLs not in CRM this week (0 tweets but still partners)
    for h_lower, gs in gsheet_map.items():
        if h_lower not in imported_handles:
            display_h = gs.get('nick','') or h_lower
            kol = KOL(
                handle=h_lower, nickname=gs.get('nick',''), bd='',
                tier=gs.get('tier',''), cost=gs.get('cost',0), avg_price=gs.get('avg_price',0),
                followers=gs.get('followers',0),
                okx_tweets=0, okx_impressions=0, bn_tweets=0, bn_impressions=0,
                total_tweets=0, total_impressions=0,
                okx_pos=0, okx_neg=0, okx_neu=0,
                tags=['综合'], products=[],
                is_partner=True, is_official=False,
                wallet_address=gs.get('wallet',''),
                week_date=week_date,
            )
            kol.score = calc_score(kol)
            db.add(kol)

    for p in posts_data:
        db.add(Post(**p))

    db.commit()
    partner_count = sum(1 for h in imported_handles if h in gsheet_map) + sum(1 for h in gsheet_map if h not in imported_handles)
    db.close()
    return {"kols": len(kol_map), "posts": len(posts_data), "partners": partner_count, "week": week_date}

# ===== CLAUDE API =====
async def call_claude(prompt: str, system: str = "") -> str:
    if not ANTHROPIC_API_KEY:
        return "❌ 未配置 ANTHROPIC_API_KEY"
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post("https://api.anthropic.com/v1/messages", json={
                "model": "claude-sonnet-4-20250514", "max_tokens": 1000,
                "system": system or "你是OKX Builder Eye的AI分析助手。简洁、数据驱动、中文回答。",
                "messages": [{"role":"user","content":prompt}],
            }, headers={"x-api-key":ANTHROPIC_API_KEY,"anthropic-version":"2023-06-01","content-type":"application/json"})
            data = r.json()
            if "content" in data:
                return "\n".join(c.get("text","") for c in data["content"] if c.get("type")=="text")
            return f"❌ {data.get('error',{}).get('message','未知错误')}"
    except Exception as e:
        return f"❌ {str(e)}"

# ===== FEISHU =====
async def push_feishu(text_content: str) -> dict:
    if not FEISHU_WEBHOOK:
        return {"error": "未配置 FEISHU_WEBHOOK"}
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(FEISHU_WEBHOOK, json={"msg_type":"text","content":{"text":text_content}})
            return r.json()
    except Exception as e:
        return {"error": str(e)}

# ===== FASTAPI APP =====
app = FastAPI(title="Builder Eye v5.0", docs_url="/docs")

@app.on_event("startup")
def startup():
    init_db()

# --- Helper ---
def fmt(n):
    if n >= 1e6: return f"{n/1e6:.1f}M"
    if n >= 1e3: return f"{n/1e3:.1f}K"
    return str(n)

def db_kols(partner_only=None):
    db = get_db()
    if not db: return []
    q = db.query(KOL).filter(KOL.is_official==False)
    if partner_only is True: q = q.filter(KOL.is_partner==True)
    elif partner_only is False: q = q.filter(KOL.is_partner==False)
    kols = q.all()
    db.close()
    return kols

def db_posts(mention=None):
    db = get_db()
    if not db: return []
    q = db.query(Post)
    if mention: q = q.filter(Post.mentions.cast(String).ilike(f'%{mention}%'))
    posts = q.order_by(Post.impressions.desc()).all()
    db.close()
    return posts

# ===== API ROUTES =====

@app.get("/api/stats")
def get_stats():
    partners = db_kols(True)
    non_partners = db_kols(False)
    ot = sum(k.okx_tweets for k in partners)
    oi = sum(k.okx_impressions for k in partners)
    bt = sum(k.bn_tweets for k in partners)
    bi = sum(k.bn_impressions for k in partners)
    # BD
    bd_map = {}
    for k in partners:
        if k.bd not in bd_map: bd_map[k.bd] = {"bd":k.bd,"n":0,"ot":0,"oi":0,"bt":0,"bi":0}
        b = bd_map[k.bd]; b["n"]+=1; b["ot"]+=k.okx_tweets; b["oi"]+=k.okx_impressions; b["bt"]+=k.bn_tweets; b["bi"]+=k.bn_impressions
    # Sentiment
    posts = db_posts("okx")
    sent = {"pos":0,"neg":0,"neu":0}
    for p in posts:
        if p.sentiment>0: sent["pos"]+=1
        elif p.sentiment<0: sent["neg"]+=1
        else: sent["neu"]+=1
    # Daily
    daily = {}
    for p in posts:
        d = p.published_at[:10] if p.published_at else ""
        if d:
            if d not in daily: daily[d] = {"count":0,"imp":0}
            daily[d]["count"]+=1; daily[d]["imp"]+=p.impressions
    return {
        "partners":len(partners),"non_partners":len(non_partners),
        "okx_tweets":ot,"okx_imp":oi,"bn_tweets":bt,"bn_imp":bi,
        "ratio":round(ot/bt,2) if bt else 0,
        "sentiment":sent,"bd":sorted(bd_map.values(),key=lambda x:-x["oi"]),
        "daily":dict(sorted(daily.items())),
        "scored_ok":sum(1 for k in partners if k.score>=60),
        "orbit_joined":sum(1 for k in partners if k.orbit_status=="joined"),
    }

@app.get("/api/partners")
def get_partners(tag:str=Query("all"),bd:str=Query("all"),search:str=Query(""),sort:str=Query("okx_imp")):
    kols = db_kols(True)
    results = []
    for k in kols:
        tags = k.tags or []
        if tag!="all" and tag not in tags: continue
        if bd!="all" and k.bd!=bd: continue
        if search and search.lower() not in k.handle.lower() and search.lower() not in (k.nickname or '').lower() and search.lower() not in k.bd.lower(): continue
        results.append({
            "handle":k.handle,"nick":k.nickname or k.handle,"bd":k.bd,"tier":k.tier,
            "cost":k.cost,"okx_t":k.okx_tweets,"okx_i":k.okx_impressions,
            "bn_t":k.bn_tweets,"bn_i":k.bn_impressions,"total_t":k.total_tweets,
            "tags":tags,"prods":k.products or [],"score":k.score,
            "status":"active" if k.score>=60 else ("warning" if k.score>=35 else "danger"),
            "orbit":k.orbit_status,
        })
    sk = {"okx_imp":lambda x:-x["okx_i"],"score":lambda x:-x["score"],"bn_t":lambda x:-x["bn_t"]}.get(sort,lambda x:-x["okx_i"])
    results.sort(key=sk)
    return {"partners":results,"total":len(results)}

@app.get("/api/non-partners")
def get_non_partners(sort:str=Query("total")):
    kols = db_kols(False)
    results = [{"handle":k.handle,"nick":k.nickname or k.handle,"bd":k.bd,
                "okx_t":k.okx_tweets,"okx_i":k.okx_impressions,"bn_t":k.bn_tweets,"bn_i":k.bn_impressions,
                "total_i":k.okx_impressions+k.bn_impressions,"tags":k.tags or []}
               for k in kols]
    sk = {"total":lambda x:-x["total_i"],"bn_i":lambda x:-x["bn_i"],"okx_i":lambda x:-x["okx_i"]}.get(sort,lambda x:-x["total_i"])
    results.sort(key=sk)
    return {"kols":results,"total":len(results)}

@app.get("/api/posts")
def get_posts(mention:str=Query("okx"),limit:int=Query(30)):
    posts = db_posts(mention)
    nm = {k.handle.lower():k.nickname for k in db_kols() if k.nickname}
    return {"posts":[{
        "handle":p.handle,"nick":nm.get(p.handle.lower(),p.handle),
        "imp":p.impressions,"likes":p.likes,"comments":p.comments,
        "sentiment":p.sentiment,"desc":p.description[:200],"link":p.link,
        "date":p.published_at[:10] if p.published_at else "","prods":p.products_mentioned or [],
    } for p in posts[:limit]]}

@app.get("/api/products")
def get_products():
    posts = db_posts("okx")
    nm = {k.handle.lower():k.nickname for k in db_kols() if k.nickname}
    pm = {}
    for p in posts:
        for pr in (p.products_mentioned or []):
            if pr not in pm: pm[pr] = {"name":pr,"count":0,"imp":0,"kols":set()}
            pm[pr]["count"]+=1; pm[pr]["imp"]+=p.impressions; pm[pr]["kols"].add(p.handle)
    return {"products":[{"name":v["name"],"count":v["count"],"imp":v["imp"],
             "kol_count":len(v["kols"]),"kols":[{"h":h,"nick":nm.get(h.lower(),h)} for h in list(v["kols"])[:10]]}
            for v in sorted(pm.values(),key=lambda x:-x["count"])]}

@app.post("/api/upload")
async def upload_crm(crm_file: UploadFile = File(...), gsheet_file: UploadFile = File(None)):
    crm_bytes = await crm_file.read()
    gsheet_bytes = await gsheet_file.read() if gsheet_file else None
    result = parse_and_import(crm_bytes, gsheet_bytes)
    return result

@app.post("/api/orbit/update")
def update_orbit(handle: str = Query(...), status: str = Query(...)):
    db = get_db()
    if not db: return {"error":"no db"}
    kol = db.query(KOL).filter(KOL.handle==handle).first()
    if kol:
        kol.orbit_status = status
        kol.updated_at = datetime.utcnow()
        db.commit()
    db.close()
    return {"ok":True,"handle":handle,"status":status}

@app.post("/api/ai/discover")
async def ai_discover(track: str = Query("all")):
    kols = db_kols(False)
    kols.sort(key=lambda k:-(k.okx_impressions+k.bn_impressions))
    data_str = "\n".join(f"@{k.handle}: OKX{k.okx_tweets}条/{fmt(k.okx_impressions)}曝光, BN{k.bn_tweets}条/{fmt(k.bn_impressions)}曝光, 赛道{k.tags}" for k in kols[:15])
    prompt = f"以下是CRM中非合作的高曝光KOL:\n{data_str}\n\n推荐TOP5最值得建立合作的，每个给出推荐理由和切入角度。简洁有力。"
    result = await call_claude(prompt)
    return {"result":result}

@app.post("/api/ai/builder")
async def ai_builder():
    kols = db_kols(True)
    kols.sort(key=lambda k:-k.score)
    data_str = "\n".join(f"@{k.handle}({k.nickname}): 绩效{k.score}, OKX{k.okx_tweets}条/{fmt(k.okx_impressions)}, BN{k.bn_tweets}条" for k in kols[:30])
    prompt = f"Builder绩效数据:\n{data_str}\n\n分析:1.优秀者 2.建议淘汰者 3.整体健康度。标准:每月≥4条OKX推文，BN不应远超OKX。"
    result = await call_claude(prompt)
    return {"result":result}

@app.post("/api/ai/orbit")
async def ai_orbit():
    kols = db_kols(True)
    joined = sum(1 for k in kols if k.orbit_status=="joined")
    prompt = f"Builder{len(kols)}人，Orbit已入驻{joined}({joined/max(len(kols),1)*100:.0f}%)。给出:1.催促话术 2.提升方案 3.本周行动清单。"
    result = await call_claude(prompt)
    return {"result":result}

@app.post("/api/ai/conversion")
async def ai_conversion():
    prods = get_products()["products"]
    prod_str = ", ".join(f"{p['name']}:{p['count']}条/{p['kol_count']}KOL" for p in prods[:8])
    prompt = f"产品分布:{prod_str}\n分析:1.哪些被真正使用 2.渗透率提升建议 3.链上验证机制设计。"
    result = await call_claude(prompt)
    return {"result":result}

@app.post("/api/push/weekly")
async def push_weekly():
    stats = get_stats()
    text = f"📊 Builder Eye 周报\n\n合作KOL:{stats['partners']} | OKX:{stats['okx_tweets']}条/{fmt(stats['okx_imp'])}\nBN:{stats['bn_tweets']}条 | 比值:{stats['ratio']}\n绩效达标:{stats['scored_ok']}/{stats['partners']}\nOrbit入驻:{stats['orbit_joined']}"
    result = await push_feishu(text)
    return result

# ===== FRONTEND =====
@app.get("/", response_class=HTMLResponse)
def index():
    return """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Builder Eye v5.0</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://unpkg.com/alpinejs@3" defer></script>
<style>
body{background:#0a0a0f;color:#e8e8f0;font-family:'Noto Sans SC',system-ui,sans-serif}
::-webkit-scrollbar{width:5px}::-webkit-scrollbar-thumb{background:#2a2a42;border-radius:3px}
.card{background:#12121a;border:1px solid #2a2a42;border-radius:14px;padding:16px}
.tbl{width:100%;border-collapse:collapse;font-size:12px}
.tbl th{text-align:left;padding:6px 8px;color:#6868a0;font-size:10px;text-transform:uppercase;border-bottom:1px solid #2a2a42;position:sticky;top:0;background:#12121a}
.tbl td{padding:5px 8px;border-bottom:1px solid rgba(42,42,66,.3)}
.tbl tr:hover td{background:rgba(0,212,170,.04)}
a.kl{color:#4dabf7;text-decoration:none}a.kl:hover{text-decoration:underline}
.acc{color:#00d4aa}.bn{color:#f0b90b}.wrn{color:#ff6b6b}
.tag{display:inline-block;padding:1px 6px;border-radius:3px;font-size:9px;font-weight:600;margin:1px;background:rgba(0,212,170,.15);color:#00d4aa}
.sbdg{display:inline-block;padding:1px 6px;border-radius:4px;font-size:10px;font-weight:700}
.sbdg-h{background:rgba(0,212,170,.2);color:#00d4aa}.sbdg-m{background:rgba(255,212,59,.2);color:#ffd43b}.sbdg-l{background:rgba(255,107,107,.2);color:#ff6b6b}
.st{display:inline-block;padding:2px 8px;border-radius:10px;font-size:9px;font-weight:600}
.st-a{background:rgba(0,212,170,.15);color:#00d4aa}.st-w{background:rgba(255,212,59,.15);color:#ffd43b}.st-d{background:rgba(255,107,107,.15);color:#ff6b6b}
.nb{padding:6px 14px;border-radius:8px;cursor:pointer;font-size:12px;font-weight:500;border:none;transition:all .2s}
.nb:hover{background:#1a1a28;color:#e8e8f0}
.ai-box{background:#1a1a28;border:1px solid #2a2a42;border-radius:10px;padding:14px;min-height:60px;font-size:12px;white-space:pre-wrap;line-height:1.6}
.btn{padding:7px 14px;border-radius:8px;font-size:12px;font-weight:600;cursor:pointer;border:none;transition:all .2s}
.btn-ai{background:linear-gradient(135deg,#a78bfa,#4dabf7);color:#fff}
.btn-p{background:#00d4aa;color:#0a0a0f}.btn-s{background:#1a1a28;color:#e8e8f0;border:1px solid #2a2a42}
</style></head>
<body x-data="app()" x-init="init()">

<!-- Header -->
<div class="sticky top-0 z-50 border-b border-[#2a2a42] px-6 py-3 flex justify-between items-center flex-wrap gap-2" style="background:linear-gradient(135deg,#12121a,#0d1520)">
  <div class="flex items-center gap-3">
    <div class="w-9 h-9 rounded-xl flex items-center justify-center font-black text-[#0a0a0f]" style="background:linear-gradient(135deg,#00d4aa,#4dabf7)">B</div>
    <div><div class="text-lg font-bold">OKX Builder <span class="acc">Eye</span> v5.0</div>
    <div class="text-[10px] text-[#6868a0] font-mono" x-text="'合作 '+stats.partners+' · 候选 '+stats.non_partners+' · OKX/BN '+stats.ratio"></div></div>
  </div>
  <div class="flex gap-1 flex-wrap">
    <template x-for="t in tabs" :key="t.id">
      <button class="nb" :class="tab===t.id?'!bg-[#00d4aa] !text-[#0a0a0f] !font-bold':'text-[#9898b0]'" @click="tab=t.id" x-text="t.icon+' '+t.name"></button>
    </template>
    <button class="btn btn-s ml-2" @click="pushWeekly()">📮 飞书</button>
  </div>
</div>

<!-- Stats Row -->
<div class="grid grid-cols-6 gap-2 px-6 py-3">
  <template x-for="s in statCards" :key="s.label">
    <div class="card !p-3 hover:border-[#00d4aa] transition">
      <div class="text-[9px] text-[#6868a0] uppercase tracking-wider" x-text="s.label"></div>
      <div class="text-xl font-bold font-mono" :class="s.cls" x-text="s.value"></div>
      <div class="text-[9px] text-[#9898b0] mt-1" x-text="s.sub"></div>
    </div>
  </template>
</div>

<!-- Tab Content -->
<div class="px-6 pb-6">

  <!-- OVERVIEW -->
  <div x-show="tab==='ov'" x-transition>
    <div class="grid grid-cols-2 gap-3 mb-3">
      <div class="card"><div class="text-sm font-semibold mb-3">🏆 OKX TOP KOL</div>
        <div class="max-h-80 overflow-y-auto"><table class="tbl"><thead><tr><th>#</th><th>昵称</th><th>BD</th><th>OKX</th><th>曝光</th><th>绩效</th></tr></thead>
        <tbody><template x-for="(k,i) in partners.slice(0,15)" :key="k.handle"><tr>
          <td x-text="i+1"></td><td><a class="kl" :href="'https://x.com/'+k.handle" target="_blank" x-text="k.nick"></a> <span class="text-[8px] text-[#6868a0]" x-text="'@'+k.handle"></span></td>
          <td class="text-[9px]" x-text="k.bd.split(' ')[0]"></td><td x-text="k.okx_t"></td><td class="acc font-mono" x-text="fmtN(k.okx_i)"></td>
          <td><span class="sbdg" :class="k.score>=60?'sbdg-h':k.score>=35?'sbdg-m':'sbdg-l'" x-text="k.score"></span></td>
        </tr></template></tbody></table></div>
      </div>
      <div class="card"><div class="text-sm font-semibold mb-3">🔥 OKX 热门推文 <span class="font-normal text-[#6868a0]">(点击跳原文)</span></div>
        <div class="max-h-80 overflow-y-auto"><table class="tbl"><thead><tr><th>#</th><th>昵称</th><th>曝光</th><th>日期</th><th></th></tr></thead>
        <tbody><template x-for="(p,i) in okxPosts.slice(0,12)" :key="i"><tr>
          <td x-text="i+1"></td><td><a class="kl" :href="'https://x.com/'+p.handle" target="_blank" x-text="p.nick"></a></td>
          <td class="acc font-mono" x-text="fmtN(p.imp)"></td><td class="text-[9px]" x-text="p.date.slice(5)"></td>
          <td><a class="text-[#4dabf7] text-[10px]" :href="p.link" target="_blank">↗ 原文</a></td>
        </tr></template></tbody></table></div>
      </div>
    </div>
    <div class="grid grid-cols-2 gap-3">
      <div class="card"><div class="text-sm font-semibold mb-3 bn">💛 Binance TOP KOL — <span class="font-normal text-[#6868a0]">发现竞对合作机会</span></div>
        <div class="max-h-72 overflow-y-auto"><table class="tbl"><thead><tr><th>#</th><th>昵称</th><th>BN条</th><th>BN曝光</th><th>状态</th></tr></thead>
        <tbody><template x-for="(p,i) in bnPosts.slice(0,12)" :key="i"><tr>
          <td x-text="i+1"></td><td><a class="kl" :href="'https://x.com/'+p.handle" target="_blank" x-text="p.nick"></a></td>
          <td class="bn" x-text="p.imp?fmtN(p.imp):'-'"></td><td class="bn font-mono" x-text="fmtN(p.imp)"></td>
          <td class="text-[9px]"><a class="text-[#4dabf7]" :href="p.link" target="_blank">↗</a></td>
        </tr></template></tbody></table></div>
      </div>
      <div class="card"><div class="text-sm font-semibold mb-3">📦 产品速览</div>
        <div class="max-h-72 overflow-y-auto"><table class="tbl"><thead><tr><th>产品</th><th>推文</th><th>曝光</th><th>KOL</th></tr></thead>
        <tbody><template x-for="p in products" :key="p.name"><tr>
          <td class="font-semibold" x-text="p.name"></td><td class="acc" x-text="p.count"></td><td class="acc font-mono" x-text="fmtN(p.imp)"></td><td x-text="p.kol_count"></td>
        </tr></template></tbody></table></div>
      </div>
    </div>
  </div>

  <!-- PARTNERS -->
  <div x-show="tab==='kol'" x-transition>
    <div class="flex gap-2 mb-3 flex-wrap items-center">
      <input class="bg-[#1a1a28] border border-[#2a2a42] rounded-lg px-3 py-1.5 text-sm w-48 focus:border-[#00d4aa] outline-none" placeholder="🔍 搜索昵称/handle..." x-model="kolSearch" @input="loadPartners()">
      <select class="bg-[#1a1a28] border border-[#2a2a42] rounded-lg px-2 py-1.5 text-sm" x-model="kolBD" @change="loadPartners()">
        <option value="all">全部BD</option>
        <template x-for="b in bdList" :key="b"><option :value="b" x-text="b.split(' ')[0]"></option></template>
      </select>
      <select class="bg-[#1a1a28] border border-[#2a2a42] rounded-lg px-2 py-1.5 text-sm" x-model="kolSort" @change="loadPartners()">
        <option value="okx_imp">OKX曝光↓</option><option value="score">绩效分↓</option><option value="bn_t">BN条数↓</option>
      </select>
      <button class="btn btn-ai" @click="aiBuilder()">🤖 AI 淘汰分析</button>
    </div>
    <div class="grid grid-cols-[1fr_320px] gap-3">
      <div class="card"><div class="text-sm font-semibold mb-3">👥 合作 KOL (<span x-text="partners.length"></span>)</div>
        <div class="max-h-[520px] overflow-y-auto"><table class="tbl"><thead><tr><th>#</th><th>昵称</th><th>层级</th><th>BD</th><th>OKX条</th><th>OKX曝光</th><th>BN条</th><th>费用</th><th>绩效</th><th>状态</th></tr></thead>
        <tbody><template x-for="(k,i) in partners" :key="k.handle"><tr>
          <td x-text="i+1"></td>
          <td><a class="kl" :href="'https://x.com/'+k.handle" target="_blank" x-text="k.nick"></a> <span class="text-[8px] text-[#6868a0]" x-text="'@'+k.handle"></span></td>
          <td class="font-bold text-sm" :style="{color:{'S':'#00d4aa','A':'#4dabf7','B':'#ffd43b','C':'#6868a0'}[k.tier]||'#6868a0'}" x-text="k.tier||'-'"></td>
          <td class="text-[9px]" x-text="k.bd.split(' ')[0]"></td>
          <td class="acc" x-text="k.okx_t"></td><td class="acc font-mono" x-text="fmtN(k.okx_i)"></td>
          <td class="bn" x-text="k.bn_t"></td><td class="font-mono text-[10px]" x-text="k.cost?k.cost+'U':'-'"></td>
          <td><span class="sbdg" :class="k.score>=60?'sbdg-h':k.score>=35?'sbdg-m':'sbdg-l'" x-text="k.score"></span></td>
          <td><span class="st" :class="k.score>=60?'st-a':k.score>=35?'st-w':'st-d'" x-text="k.score>=60?'达标':k.score>=35?'观察':'淘汰'"></span></td>
        </tr></template></tbody></table></div>
      </div>
      <div>
        <div class="card mb-3"><div class="text-sm font-semibold mb-2">📊 BD 维度</div>
          <template x-for="b in stats.bd" :key="b.bd"><div class="mb-3">
            <div class="text-[11px] font-semibold mb-1" x-text="b.bd.split(' ')[0]+' ('+b.n+')'"></div>
            <div class="flex items-center gap-1 mb-1"><span class="text-[8px] w-7 text-right acc">OKX</span><div class="flex-1 h-4 bg-[#1a1a28] rounded"><div class="h-full rounded acc" :style="{width:(b.oi/Math.max(...stats.bd.map(x=>Math.max(x.oi,x.bi)))*100)+'%',background:'linear-gradient(90deg,#00d4aa,#00b894)'}"></div></div></div>
            <div class="flex items-center gap-1"><span class="text-[8px] w-7 text-right bn">BN</span><div class="flex-1 h-4 bg-[#1a1a28] rounded"><div class="h-full rounded" :style="{width:(b.bi/Math.max(...stats.bd.map(x=>Math.max(x.oi,x.bi)))*100)+'%',background:'linear-gradient(90deg,#f0b90b,#e0a800)'}"></div></div></div>
          </div></template>
        </div>
        <div class="card"><div class="text-sm font-semibold mb-2">🤖 AI 分析</div><div class="ai-box" x-html="aiBuilderResult||'<span class=text-[#6868a0]>点击上方按钮获取AI分析...</span>'"></div></div>
      </div>
    </div>
  </div>

  <!-- PRODUCTS -->
  <div x-show="tab==='prod'" x-transition>
    <div class="grid grid-cols-3 gap-3 mb-3">
      <template x-for="p in products" :key="p.name"><div class="card">
        <div class="font-semibold text-sm mb-1" x-text="p.name"></div>
        <div class="flex gap-3 text-[11px] text-[#9898b0]">推文 <b class="acc" x-text="p.count"></b> · 曝光 <b class="acc" x-text="fmtN(p.imp)"></b> · KOL <b x-text="p.kol_count"></b></div>
      </div></template>
    </div>
  </div>

  <!-- DISCOVER -->
  <div x-show="tab==='disc'" x-transition>
    <div class="flex gap-2 mb-3 items-center">
      <select class="bg-[#1a1a28] border border-[#2a2a42] rounded-lg px-2 py-1.5 text-sm" x-model="discSort" @change="loadNonPartners()">
        <option value="total">总曝光↓</option><option value="bn_i">BN曝光↓</option><option value="okx_i">OKX曝光↓</option>
      </select>
      <button class="btn btn-ai" @click="aiDiscover()">🤖 AI 推荐合作</button>
    </div>
    <div class="grid grid-cols-[1fr_360px] gap-3">
      <div class="card"><div class="text-sm font-semibold mb-3">🔭 候选 KOL (<span x-text="nonPartners.length"></span>)</div>
        <div class="max-h-[500px] overflow-y-auto"><table class="tbl"><thead><tr><th>#</th><th>KOL</th><th>OKX条</th><th>OKX曝光</th><th>BN条</th><th>BN曝光</th><th>总曝光</th><th>赛道</th><th>BD</th></tr></thead>
        <tbody><template x-for="(k,i) in nonPartners" :key="k.handle"><tr class="bg-[rgba(77,171,247,.03)]">
          <td x-text="i+1"></td><td><a class="kl" :href="'https://x.com/'+k.handle" target="_blank" x-text="k.nick||k.handle"></a></td>
          <td class="acc" x-text="k.okx_t"></td><td class="acc font-mono" x-text="fmtN(k.okx_i)"></td>
          <td class="bn" x-text="k.bn_t"></td><td class="bn font-mono" x-text="fmtN(k.bn_i)"></td>
          <td class="font-bold" x-text="fmtN(k.total_i)"></td>
          <td><template x-for="t in (k.tags||[]).slice(0,2)" :key="t"><span class="tag" x-text="t"></span></template></td>
          <td class="text-[9px]" x-text="k.bd.split(' ')[0]"></td>
        </tr></template></tbody></table></div>
      </div>
      <div class="card"><div class="text-sm font-semibold mb-2">🤖 AI 推荐</div><div class="ai-box" x-html="aiDiscoverResult||'<span class=text-[#6868a0]>点击按钮获取推荐...</span>'"></div></div>
    </div>
  </div>

  <!-- ORBIT -->
  <div x-show="tab==='orb'" x-transition>
    <div class="grid grid-cols-2 gap-3">
      <div class="card"><div class="text-sm font-semibold mb-3">🪐 Orbit 入驻追踪</div>
        <div class="mb-3"><div class="text-[10px] text-[#6868a0] mb-1">入驻进度</div>
          <div class="flex items-center gap-2"><div class="flex-1 h-2 bg-[#1a1a28] rounded-full overflow-hidden"><div class="h-full rounded-full" style="background:linear-gradient(90deg,#a78bfa,#00d4aa)" :style="{width:(stats.orbit_joined/Math.max(stats.partners,1)*100)+'%'}"></div></div>
          <span class="text-xs font-bold acc" x-text="stats.orbit_joined+'/'+stats.partners"></span></div>
        </div>
        <div class="max-h-96 overflow-y-auto"><table class="tbl"><thead><tr><th>昵称</th><th>OKX条</th><th>状态</th><th>操作</th></tr></thead>
        <tbody><template x-for="k in partners.filter(k=>k.okx_t>=1)" :key="k.handle"><tr>
          <td><a class="kl" :href="'https://x.com/'+k.handle" target="_blank" x-text="k.nick"></a></td>
          <td class="acc" x-text="k.okx_t"></td>
          <td><span class="st" :class="k.orbit==='joined'?'st-a':k.orbit==='invited'?'st-w':''" x-text="k.orbit==='joined'?'🪐 已入驻':k.orbit==='invited'?'📨 已邀请':'❓ 未邀请'"></span></td>
          <td><select class="bg-[#1a1a28] text-white border border-[#2a2a42] rounded text-[9px] px-1" :value="k.orbit" @change="setOrbit(k.handle,$event.target.value)">
            <option value="none">未邀请</option><option value="invited">已邀请</option><option value="joined">已入驻</option>
          </select></td>
        </tr></template></tbody></table></div>
      </div>
      <div>
        <div class="card mb-3" style="font-size:11px;color:#9898b0;line-height:1.8">
          <div class="text-sm font-semibold mb-2 text-white">📜 合作条款</div>
          ① 合作期内完成 Orbit 入驻<br>② 每月≥2条 Orbit 推文<br>③ 推文含链接/截图<br>④ TOP3 额外奖金<br>⑤ 未达标扣减 10%
        </div>
        <div class="card"><div class="text-sm font-semibold mb-2">🤖 AI 策略</div>
          <button class="btn btn-ai mb-2" @click="aiOrbit()">🤖 生成推广策略</button>
          <div class="ai-box" x-html="aiOrbitResult||'<span class=text-[#6868a0]>...</span>'"></div>
        </div>
      </div>
    </div>
  </div>

  <!-- CONVERSION -->
  <div x-show="tab==='conv'" x-transition>
    <div class="grid grid-cols-3 gap-3 mb-3">
      <div class="card"><div class="text-sm font-semibold mb-3">📊 漏斗</div>
        <template x-for="(f,i) in funnel" :key="f.label"><div class="mb-2">
          <div class="flex justify-between text-[10px] mb-1"><span x-text="f.label"></span><span class="font-bold" :style="{color:f.color}" x-text="f.value"></span></div>
          <div class="h-4 bg-[#1a1a28] rounded"><div class="h-full rounded" :style="{width:f.pct+'%',background:f.color,opacity:1-i*.15}"></div></div>
        </div></template>
      </div>
      <div class="card"><div class="text-sm font-semibold mb-3">🔗 使用真实度</div>
        <div class="space-y-2">
          <div class="p-2 bg-[#1a1a28] rounded">📝 推文层 <span class="st st-a">已实现</span></div>
          <div class="p-2 bg-[#1a1a28] rounded">🛠 产品层 <span class="st st-a">已实现</span></div>
          <div class="p-2 bg-[#1a1a28] rounded">🔗 链上层 <span class="st st-w">待接入</span></div>
          <div class="p-2 bg-[#1a1a28] rounded">📊 UID层 <span class="st st-d">待打通</span></div>
        </div>
      </div>
      <div class="card"><div class="text-sm font-semibold mb-3">🤖 AI 转化</div>
        <button class="btn btn-ai mb-2" @click="aiConversion()">🤖 分析</button>
        <div class="ai-box" x-html="aiConvResult||'<span class=text-[#6868a0]>...</span>'"></div>
      </div>
    </div>
  </div>

</div>

<!-- Upload Modal -->
<div x-show="showUpload" class="fixed inset-0 bg-black/70 flex items-center justify-center z-50" @click.self="showUpload=false">
  <div class="card w-[480px]">
    <h3 class="text-lg font-bold mb-4">📤 上传数据</h3>
    <div class="mb-3"><label class="text-xs text-[#6868a0] block mb-1">CRM周报 Excel (必须)</label>
      <input type="file" accept=".xlsx" class="text-sm" @change="crmFile=$event.target.files[0]"></div>
    <div class="mb-4"><label class="text-xs text-[#6868a0] block mb-1">Google Sheet KOL数据库 (可选)</label>
      <input type="file" accept=".xlsx" class="text-sm" @change="gsFile=$event.target.files[0]"></div>
    <div class="flex gap-2">
      <button class="btn btn-p" @click="doUpload()" :disabled="!crmFile">上传并导入</button>
      <button class="btn btn-s" @click="showUpload=false">取消</button>
    </div>
    <div class="text-xs mt-2 text-[#6868a0]" x-text="uploadMsg"></div>
  </div>
</div>

<script>
function app(){return{
  tab:'ov',
  tabs:[{id:'ov',icon:'📊',name:'总览'},{id:'kol',icon:'👥',name:'合作KOL'},{id:'prod',icon:'🛠',name:'产品'},{id:'disc',icon:'🔭',name:'发现'},{id:'orb',icon:'🪐',name:'Orbit'},{id:'conv',icon:'📊',name:'转化'}],
  stats:{partners:0,non_partners:0,okx_tweets:0,okx_imp:0,bn_tweets:0,bn_imp:0,ratio:0,sentiment:{},bd:[],daily:{},scored_ok:0,orbit_joined:0},
  statCards:[],
  partners:[],nonPartners:[],okxPosts:[],bnPosts:[],products:[],
  kolSearch:'',kolBD:'all',kolSort:'okx_imp',discSort:'total',
  bdList:[],
  aiBuilderResult:'',aiDiscoverResult:'',aiOrbitResult:'',aiConvResult:'',
  funnel:[],
  showUpload:false,crmFile:null,gsFile:null,uploadMsg:'',

  fmtN(n){return n>=1e6?(n/1e6).toFixed(1)+'M':n>=1e3?(n/1e3).toFixed(1)+'K':String(n)},

  async init(){
    await this.loadStats();
    await this.loadPartners();
    await this.loadNonPartners();
    await this.loadPosts();
    await this.loadProducts();
  },

  async loadStats(){
    const r=await fetch('/api/stats').then(r=>r.json());
    this.stats=r;
    this.bdList=[...new Set(r.bd.map(b=>b.bd))];
    this.statCards=[
      {label:'合作KOL',value:r.partners,cls:'text-[#4dabf7]',sub:r.bd.length+' BD'},
      {label:'OKX推文',value:r.okx_tweets,cls:'acc',sub:'曝光 '+this.fmtN(r.okx_imp)},
      {label:'BN推文',value:r.bn_tweets,cls:'bn',sub:'曝光 '+this.fmtN(r.bn_imp)},
      {label:'OKX/BN',value:r.ratio,cls:r.ratio>=0.3?'acc':'wrn',sub:'目标≥0.5'},
      {label:'绩效达标',value:r.scored_ok+'/'+r.partners,cls:'acc',sub:''},
      {label:'Orbit入驻',value:r.orbit_joined,cls:'text-[#a78bfa]',sub:''},
    ];
    const tOT=r.okx_tweets,pM=Object.values(this.products).reduce((s,p)=>s+(p.count||0),0);
    this.funnel=[
      {label:'OKX推文',value:r.okx_tweets,color:'#00d4aa',pct:100},
      {label:'提及产品',value:'...',color:'#4dabf7',pct:40},
      {label:'含链接',value:'...',color:'#a78bfa',pct:20},
      {label:'链接点击',value:'(需UTM)',color:'#6868a0',pct:8},
    ];
  },

  async loadPartners(){
    const r=await fetch(`/api/partners?tag=all&bd=${this.kolBD}&search=${this.kolSearch}&sort=${this.kolSort}`).then(r=>r.json());
    this.partners=r.partners;
  },

  async loadNonPartners(){
    const r=await fetch(`/api/non-partners?sort=${this.discSort}`).then(r=>r.json());
    this.nonPartners=r.kols;
  },

  async loadPosts(){
    const r1=await fetch('/api/posts?mention=okx&limit=15').then(r=>r.json());
    this.okxPosts=r1.posts;
    const r2=await fetch('/api/posts?mention=binance&limit=15').then(r=>r.json());
    this.bnPosts=r2.posts;
  },

  async loadProducts(){
    const r=await fetch('/api/products').then(r=>r.json());
    this.products=r.products;
    if(this.stats.okx_tweets){
      const pm=r.products.reduce((s,p)=>s+p.count,0);
      this.funnel=[
        {label:'OKX推文',value:this.stats.okx_tweets,color:'#00d4aa',pct:100},
        {label:'提及产品',value:pm,color:'#4dabf7',pct:Math.round(pm/this.stats.okx_tweets*100)},
        {label:'含链接',value:'~'+Math.round(pm*.5),color:'#a78bfa',pct:Math.round(pm*.5/this.stats.okx_tweets*100)},
        {label:'点击/注册',value:'(需UTM/UID)',color:'#6868a0',pct:5},
      ];
    }
  },

  async setOrbit(handle,status){
    await fetch(`/api/orbit/update?handle=${handle}&status=${status}`,{method:'POST'});
    await this.loadPartners();
    await this.loadStats();
  },

  async aiBuilder(){
    this.aiBuilderResult='<span class="text-[#6868a0]">🤖 分析中...</span>';
    const r=await fetch('/api/ai/builder',{method:'POST'}).then(r=>r.json());
    this.aiBuilderResult=r.result;
  },
  async aiDiscover(){
    this.aiDiscoverResult='<span class="text-[#6868a0]">🤖 分析中...</span>';
    const r=await fetch('/api/ai/discover?track=all',{method:'POST'}).then(r=>r.json());
    this.aiDiscoverResult=r.result;
  },
  async aiOrbit(){
    this.aiOrbitResult='<span class="text-[#6868a0]">🤖 生成中...</span>';
    const r=await fetch('/api/ai/orbit',{method:'POST'}).then(r=>r.json());
    this.aiOrbitResult=r.result;
  },
  async aiConversion(){
    this.aiConvResult='<span class="text-[#6868a0]">🤖 分析中...</span>';
    const r=await fetch('/api/ai/conversion',{method:'POST'}).then(r=>r.json());
    this.aiConvResult=r.result;
  },

  async pushWeekly(){
    const r=await fetch('/api/push/weekly',{method:'POST'}).then(r=>r.json());
    alert(r.error?'推送失败: '+r.error:'✅ 飞书推送成功');
  },

  async doUpload(){
    if(!this.crmFile)return;
    const fd=new FormData();
    fd.append('crm_file',this.crmFile);
    if(this.gsFile)fd.append('gsheet_file',this.gsFile);
    this.uploadMsg='上传中...';
    const r=await fetch('/api/upload',{method:'POST',body:fd}).then(r=>r.json());
    if(r.error){this.uploadMsg='❌ '+r.error}
    else{this.uploadMsg=`✅ 导入完成: ${r.kols} KOL, ${r.posts} 推文, ${r.partners} 合作`;
      this.showUpload=false; await this.init();}
  },
}}
</script>
</body></html>"""

# Vercel entry point
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
