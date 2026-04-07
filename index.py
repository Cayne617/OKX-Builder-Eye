from http.server import BaseHTTPRequestHandler
import json, os

def call_claude(prompt, system="你是OKX Builder Eye的AI分析助手，专注于KOL运营数据分析。请用中文回答，简洁有力，多用数据支撑观点。"):
    import urllib.request
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return "⚠️ 未配置 ANTHROPIC_API_KEY，请在 Vercel 环境变量中设置。"
    body = json.dumps({
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 2000,
        "system": system,
        "messages": [{"role": "user", "content": prompt}]
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01"
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            return data["content"][0]["text"]
    except Exception as e:
        return f"⚠️ API调用失败: {str(e)}"

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length)) if length else {}
        action = body.get("action", "")
        data = body.get("data", {})

        prompt = ""
        if action == "builder":
            prompt = f"""分析以下KOL绩效数据，给出淘汰建议和优化方向：

合作KOL总数: {data.get('total',0)}
达标人数: {data.get('good',0)}
观察人数: {data.get('warn',0)}
建议淘汰: {data.get('bad',0)}

TOP5达标KOL: {data.get('topGood','')}
TOP5淘汰候选: {data.get('topBad','')}

请从以下维度分析：
1. 整体绩效评估（达标率是否健康）
2. 淘汰候选的具体问题和处理建议
3. 预算优化建议（哪些钱花得不值）
4. 下周行动计划"""

        elif action == "discover":
            prompt = f"""分析以下非合作KOL数据，推荐最值得签约的候选人：

候选KOL列表:
{data.get('candidates','')}

请从以下维度分析：
1. 每个候选人的合作价值评估
2. 建议签约优先级排序及理由
3. 预估合作费用区间
4. 建议的合作切入方式"""

        elif action == "orbit":
            prompt = f"""Orbit星球推广数据：
入驻率: {data.get('rate','')}
活跃KOL数: {data.get('active',0)}
已入驻: {data.get('joined',0)}

请给出提升Orbit入驻率的具体策略、话术模板和本周行动计划。"""

        elif action == "conv":
            prompt = f"""产品渗透数据:
{data.get('products','')}

请分析各产品的KOL渗透效率，找出问题并给出提升转化率的具体建议。"""

        else:
            prompt = data.get("prompt", "请分析当前KOL运营数据")

        result = call_claude(prompt)

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps({"result": result}, ensure_ascii=False).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
