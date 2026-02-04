import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import requests
import numpy as np

# --- 페이지 설정 ---
st.set_page_config(page_title="Quant Screener v11.0", layout="wide")
st.title("💎 AI 퀀트 종목 발굴기 (v11.0 Final)")

with st.expander("📘 v11.0 업데이트: 매수 3단계 & 매도 신호 탑재"):
    st.markdown('''
    **전문가급 판단 로직을 적용하여 신호를 정교하게 분류했습니다.**
    
    1.  **매수 등급 세분화:**
        * **💎 인생 매수:** 지지선 3개 중첩 (확실한 기회)
        * **🔥 강력 매수:** 지지선 2개 중첩 (비중 확대)
        * **✅ 매수 고려:** 지지선 1개 (관찰 시작)
    2.  **매도(이익 실현) 신호 추가:**
        * **🚨 이익 실현:** 과매수(RSI 70+) + 저항선(R1/R2) 돌파 시
        * **📉 분할 매도:** 저항선 터치 또는 과열 조짐 시
    ''')

# --- 1. 유틸리티 함수 ---
@st.cache_data(ttl=86400)
def get_stock_name(ticker):
    hotfix_map = {
        "005930.KS": "삼성전자", "000660.KS": "SK하이닉스",
        "373220.KS": "LG에너지솔루션", "373220.KQ": "LG에너지솔루션"
    }
    if ticker.upper() in hotfix_map: return hotfix_map[ticker.upper()]
    try:
        if ".KS" in ticker or ".KQ" in ticker:
            code = ticker.split(".")[0]
            url = f"https://ac.finance.naver.com/ac?q={code}&q_enc=euc-kr&t_opts=2"
            response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=2)
            items = response.json().get('items', [])
            if items and items[0]:
                for item in items[0]:
                    if isinstance(item, list) and len(item) > 1 and item[0] == code:
                        return item[1]
    except: pass
    try:
        stock = yf.Ticker(ticker)
        return stock.info.get('shortName', ticker)
    except: return ticker

def get_pivot_points(df):
    if len(df) < 2: return 0,0,0,0,0
    last = df.iloc[-2]
    h, l, c = last['high'], last['low'], last['close']
    p = (h + l + c) / 3
    r1 = (2 * p) - l
    s1 = (2 * p) - h
    r2 = p + (h - l)
    s2 = p - (h - l)
    return p, s1, s2, r1, r2

def get_fibonacci_levels(df, period=120):
    if len(df) < period: period = len(df)
    recent = df.tail(period)
    max_h = recent['high'].max()
    min_l = recent['low'].min()
    diff = max_h - min_l
    fib_618 = max_h - (diff * 0.618)
    fib_050 = max_h - (diff * 0.5)
    return fib_618, fib_050, max_h, min_l

def get_max_vol_price(df, period=240):
    if len(df) < period: period = len(df)
    recent = df.tail(period)
    return recent.loc[recent['volume'].idxmax()]['close']

# --- 2. 데이터 저장소 (JSONBin) ---
api_key_names = ["JSONBIN_API_KEY", "jsonbin_api_key"]
bin_id_names = ["JSONBIN_BIN_ID", "jsonbin_bin_id"]
JSONBIN_API_KEY = next((st.secrets.get(key) for key in api_key_names), None)
JSONBIN_BIN_ID = next((st.secrets.get(key) for key in bin_id_names), None)

if JSONBIN_API_KEY and JSONBIN_BIN_ID:
    JSONBIN_URL = f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}"
    HEADERS = {'Content-Type': 'application/json', 'X-Master-Key': JSONBIN_API_KEY}
else: JSONBIN_URL = None

@st.cache_data(ttl=300)
def load_watchlist():
    if not JSONBIN_URL: return []
    try:
        res = requests.get(f"{JSONBIN_URL}/latest", headers=HEADERS)
        return res.json().get('record', {}).get('watchlist', [])
    except: return []

def save_watchlist(data):
    if not JSONBIN_URL: return False
    try:
        requests.put(JSONBIN_URL, headers=HEADERS, json={'watchlist': data})
        st.cache_data.clear()
        return True
    except: return False

if 'watchlist_loaded' not in st.session_state:
    st.session_state.watchlist = load_watchlist()
    st.session_state.watchlist_loaded = True

# --- 3. 사이드바 UI ---
market_choice = st.sidebar.radio("시장 선택", ('미국 증시 (US)', '한국 증시 (Korea)'), horizontal=True)
watchlist_str = ", ".join(st.session_state.watchlist)

if market_choice == '한국 증시 (Korea)':
    presets = {
        "❤️ 내 관심종목": watchlist_str,
        "💾 반도체/HBM (50종)": "005930.KS, 000660.KS, 042700.KS, 000020.KS, 028300.KQ, 058470.KQ, 403870.KQ, 095340.KQ, 005290.KS, 088800.KQ, 036540.KQ, 036930.KQ, 000990.KS, 079370.KQ, 030530.KQ, 253450.KQ, 046120.KQ, 054450.KQ, 023460.KQ, 373200.KQ, 281740.KQ, 263360.KQ, 006730.KQ, 039230.KQ, 084370.KQ, 015920.KQ, 140410.KQ, 104830.KQ, 056620.KQ, 092220.KQ, 085370.KQ, 049430.KQ, 077360.KQ, 121890.KQ, 160550.KQ, 043650.KQ, 091700.KQ, 058820.KQ, 135150.KQ, 074950.KQ, 322310.KQ, 402340.KQ, 222800.KQ, 330590.KQ, 131290.KQ, 067310.KQ, 131970.KQ, 089980.KQ, 064290.KQ, 005810.KS",
        "🔋 2차전지/리튬 (45종)": "373220.KS, 006400.KS, 051910.KS, 003670.KS, 247540.KQ, 086520.KQ, 066970.KQ, 005070.KS, 277810.KQ, 000270.KS, 096770.KS, 011790.KS, 025980.KQ, 099190.KQ, 101160.KQ, 307930.KQ, 365550.KQ, 382900.KQ, 450080.KQ, 157970.KS, 217270.KQ, 091990.KQ, 009830.KS, 009540.KS, 005950.KS, 117580.KS, 210980.KS, 034730.KS, 003620.KS, 004100.KS, 345740.KQ, 158310.KQ, 333620.KQ, 354310.KQ, 417010.KQ, 294630.KQ, 348370.KQ, 007460.KQ, 298050.KQ, 054620.KQ, 013700.KS, 020150.KQ, 024880.KS, 002960.KS, 138930.KS",
        "🤖 로봇/AI/SW (40종)": "035420.KS, 035720.KS, 251270.KS, 036570.KQ, 005940.KS, 293490.KQ, 006360.KS, 352820.KS, 454910.KS, 277810.KQ, 446360.KQ, 302430.KQ, 052420.KQ, 097870.KQ, 348210.KQ, 405350.KQ, 425420.KQ, 086960.KQ, 253840.KQ, 371460.KQ, 067000.KQ, 189980.KQ, 285130.KQ, 012510.KQ, 290550.KQ, 263750.KQ, 419530.KQ, 307950.KQ, 192080.KQ, 365270.KQ, 060250.KQ, 053800.KQ, 018260.KS, 396690.KQ, 443060.KQ, 457190.KQ, 212560.KQ, 032190.KQ, 230360.KQ, 108860.KQ",
        "💊 바이오/비만/미용 (50종)": "207940.KS, 068270.KS, 196170.KQ, 000100.KS, 326030.KQ, 214150.KQ, 000250.KS, 028300.KQ, 096530.KQ, 019170.KS, 145020.KQ, 185750.KQ, 006280.KS, 235980.KQ, 237690.KQ, 214450.KQ, 446150.KQ, 336260.KQ, 249420.KQ, 347000.KQ, 128940.KS, 009290.KS, 206650.KQ, 069620.KQ, 041960.KQ, 328130.KQ, 018670.KS, 000520.KS, 102710.KQ, 216080.KQ, 048530.KQ, 005300.KS, 092040.KQ, 194700.KQ, 048260.KQ, 214370.KQ, 078160.KQ, 307750.KQ, 145720.KQ, 042370.KQ, 053030.KQ, 067630.KQ, 003120.KS, 002270.KS, 001060.KS, 290650.KQ, 443060.KQ, 361610.KQ, 285130.KQ, 396690.KQ",
        "🛡️ 방산/조선/전력 (50종)": "012450.KS, 064350.KS, 079550.KS, 042660.KS, 005490.KS, 329180.KS, 010140.KS, 042670.KS, 004270.KS, 052690.KQ, 267250.KS, 024110.KS, 010120.KS, 000720.KS, 086280.KS, 034020.KS, 005860.KS, 084650.KQ, 008930.KS, 001150.KS, 003100.KS, 119380.KQ, 083420.KQ, 047050.KS, 001570.KS, 030190.KQ, 256840.KQ, 241710.KQ, 103140.KS, 017390.KS, 000700.KS, 006390.KS, 034220.KS, 028670.KS, 003410.KS, 000400.KS, 036460.KS, 009830.KS, 010950.KS, 000080.KS, 009450.KQ, 002380.KS, 049070.KQ, 001230.KS, 006260.KS, 034020.KS, 011070.KS, 014790.KS, 000990.KS, 298040.KS",
        "💄 K-푸드/화장품 (45종)": "271560.KS, 192820.KS, 243070.KS, 097950.KS, 003230.KS, 280360.KS, 090430.KS, 278470.KS, 004370.KS, 007310.KS, 161890.KS, 143240.KS, 031430.KS, 001800.KS, 000120.KS, 001040.KS, 002790.KS, 011170.KS, 033780.KS, 039490.KS, 001680.KS, 214390.KQ, 218410.KQ, 028050.KS, 005300.KS, 112040.KQ, 028260.KS, 145990.KS, 069960.KS, 138040.KS, 023530.KS, 004170.KS, 000080.KS, 004990.KS, 005180.KS, 267980.KQ, 032640.KS, 006840.KS, 002380.KS, 005610.KS, 004410.KS, 119610.KQ, 092150.KQ, 011500.KS, 086900.KQ",
        "🏦 금융/지주/저PBR (40종)": "105560.KS, 055550.KS, 086790.KS, 032830.KS, 316140.KS, 000810.KS, 138040.KS, 071050.KS, 005380.KS, 000270.KS, 012330.KS, 003550.KS, 009900.KS, 023160.KS, 002980.KS, 001530.KS, 003690.KS, 000050.KS, 004000.KS, 000150.KS, 003540.KS, 016360.KS, 039490.KS, 030200.KS, 003470.KS, 089050.KS, 025530.KS, 025560.KS, 012630.KS, 036700.KS, 000670.KS, 000140.KS, 001040.KS, 000120.KS, 005830.KS, 001740.KS, 001450.KS, 316140.KS, 002240.KS, 000210.KS"
    }
    caption = "💡 종목 코드 입력 (예: 005930, 247540.KQ)"
else: # 프리셋 (미국)
    presets = {
        "❤️ 내 관심종목": watchlist_str,
        "👑 M7 & AI 하드웨어 (40종)": "NVDA, AAPL, MSFT, GOOGL, AMZN, META, TSLA, NFLX, AVGO, AMD, ORCL, CRM, ADBE, INTC, QCOM, CSCO, TXN, IBM, UBER, ABNB, TSM, MU, ARM, SMCI, DELL, VRT, PSTG, AMAT, LRCX, KLAC, TER, ASML, MRVL, ON, ANET, JBL, CLS, GFS, STM, NXPI",
        "☁️ SaaS/보안/클라우드 (40종)": "PLTR, SNOW, CRWD, PANW, FTNT, ZS, MDB, DDOG, NET, PATH, HUBS, TEAM, WDAY, NOW, ADSK, ANSS, SNPS, CDNS, SHOP, SQ, U, RBLX, TTD, APP, DUOL, GTLB, CFLT, IOT, HCP, OKTA, DOCU, ZM, ESTC, FSLY, Sentinel, CYBR, TENB, VRNS, QLYS, GEN",
        "💊 비만/신약/헬스케어 (40종)": "LLY, NVO, VRTX, REGN, AMGN, PFE, MRK, JNJ, UNH, ABBV, BMY, GILD, BIIB, MRNA, BNTX, ISRG, SYK, EW, MDT, ZTS, HCA, CVS, CI, ELV, MCK, COR, DXCM, RGEN, TMO, DHR, ILMN, A, WAT, MTD, STE, BAX, BDX, BSX, CNC, HUM",
        "🛍️ 소비재/리테일/음식료 (40종)": "COST, WMT, TGT, HD, LOW, MCD, SBUX, CMG, YUM, DPZ, KO, PEP, MNST, CELH, PG, CL, KMB, EL, LULU, NKE, ONON, DECK, CROX, TJX, ROST, BKNG, MAR, HLT, H, ABNB, DAL, UAL, LUV, CCL, RCL, DIS, CMCSA, TMUS, VZ, T",
        "🛡️ 방산/우주/에너지 (40종)": "LMT, RTX, GD, BA, NOC, LHX, AXON, RKLB, PL, KTOS, GE, CAT, DE, HON, MMM, WM, RSG, EMR, ETN, PH, XOM, CVX, COP, OXY, SLB, HAL, NEE, SO, DUK, CEG, VST, NRG, ET, EPD, MPLX, KMI, LNG, CCJ, URA, XLE",
        "💰 핀테크/코인/금융 (40종)": "JPM, BAC, WFC, C, MS, GS, BLK, V, MA, AXP, PYPL, SQ, AFRM, COIN, HOOD, MSTR, MARA, CLSK, RIOT, SOFI, NU, UPST, DKNG, TOST, BILL, KKA, FOUR, GPN, FIS, FISV, COF, USB, PNC, TFC, SCHW, IBKR, CME, ICE, SPGI, MCO",
        "💵 월배당/리츠/BDC (30종)": "O, MAIN, STAG, ADC, VICI, PLD, AMT, CCI, EQIX, DLR, PSA, EXR, SPG, KIM, WELL, VTR, OHI, MPW, IRM, LAMR, ARCC, OBDC, HTGC, CSWC, TSLX, GAIN, PSEC, JEPI, JEPQ, SCHD",
        "📈 ETF & 3배 레버리지 (30종)": "SPY, QQQ, DIA, IWM, VTI, VOO, TLT, AGG, HYG, LQD, GLD, SLV, USO, UNG, DBC, XLK, XLV, XLF, XLE, XLI, TQQQ, SQQQ, SOXL, SOXS, FNGU, BULZ, NVDL, TSLL, CONL, MSTX"
    }
    caption = "💡 티커 입력 (예: NVDA, TSLA)"

preset_key = st.sidebar.selectbox("종목 프리셋", presets.keys())
tickers_input = st.sidebar.text_area
