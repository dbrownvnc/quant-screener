import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import requests
import numpy as np

# --- 페이지 설정 ---
st.set_page_config(page_title="Quant Screener v10.0", layout="wide")

st.title("💎 AI 퀀트 종목 발굴기 (v10.0 Final)")

with st.expander("📘 v10.0 알고리즘 및 업데이트 내역"):
    st.markdown('''
    **기존 v9.1의 편의성은 유지하고, 분석 엔진을 '중첩 이론(Confluence)' 기반으로 업그레이드했습니다.**
    
    1.  **피보나치(Fibonacci) 탑재:** 최근 6개월 파동의 **0.618(황금비율)** 지지 라인을 자동 산출합니다.
    2.  **이동평균선 확장:** 20일선 뿐만 아니라 **60일(수급선), 120일(경기선)** 지지 여부를 함께 봅니다.
    3.  **스마트 매물대(POC):** 최근 1년 중 **가장 많은 거래량이 터진 가격(세력 평단)**을 지지선으로 인식합니다.
    4.  **피벗 포인트 확장:** 중심선(P)과 2차 저항(R2)까지 계산하여 추세의 강도를 측정합니다.
    ''')

# --- 1. 유틸리티 함수 ---

@st.cache_data(ttl=86400)
def get_stock_name(ticker):
    # 한국 종목명 매핑 (기존 유지)
    hotfix_map = {
        "005930.KS": "삼성전자", "000660.KS": "SK하이닉스",
        "373220.KS": "LG에너지솔루션", "373220.KQ": "LG에너지솔루션"
    }
    if ticker.upper() in hotfix_map: return hotfix_map[ticker.upper()]
    
    # 네이버 금융 (한국)
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
    
    # yfinance (미국)
    try:
        stock = yf.Ticker(ticker)
        return stock.info.get('shortName', ticker)
    except: return ticker

def get_pivot_points(df):
    """피벗 포인트 (P, S1, S2, R1, R2) 계산 - v10.0 확장"""
    if len(df) < 2: return 0,0,0,0,0
    last = df.iloc[-2] # 전일 기준
    h, l, c = last['high'], last['low'], last['close']
    p = (h + l + c) / 3
    r1 = (2 * p) - l
    s1 = (2 * p) - h
    r2 = p + (h - l)
    s2 = p - (h - l)
    return p, s1, s2, r1, r2

def get_fibonacci_levels(df, period=120):
    """최근 N일 고점/저점 기준 피보나치 레벨 계산 (신규)"""
    if len(df) < period: period = len(df)
    recent_data = df.tail(period)
    max_h = recent_data['high'].max()
    min_l = recent_data['low'].min()
    diff = max_h - min_l
    
    fib_0618 = max_h - (diff * 0.618) # 황금비율 지지선
    fib_0500 = max_h - (diff * 0.5)   # 절반 되돌림
    return fib_0618, fib_0500, max_h, min_l

def get_max_vol_price(df, period=240):
    """최근 N일 중 최대 거래량이 터진 날의 종가 (세력 평단 추정 - 신규)"""
    if len(df) < period: period = len(df)
    recent_data = df.tail(period)
    max_vol_idx = recent_data['volume'].idxmax()
    return recent_data.loc[max_vol_idx]['close']

# --- 2. 데이터 저장소 (JSONBin) ---
api_key_names = ["JSONBIN_API_KEY", "jsonbin_api_key"]
bin_id_names = ["JSONBIN_BIN_ID", "jsonbin_bin_id"]
JSONBIN_API_KEY = next((st.secrets.get(key) for key in api_key_names), None)
JSONBIN_BIN_ID = next((st.secrets.get(key) for key in bin_id_names), None)

if JSONBIN_API_KEY and JSONBIN_BIN_ID:
    JSONBIN_URL = f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}"
    HEADERS = {'Content-Type': 'application/json', 'X-Master-Key': JSONBIN_API_KEY}
else:
    JSONBIN_URL = None

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

# --- 3. 사이드바 UI (기존 v9.1 프리셋 유지) ---
market_choice = st.sidebar.radio("시장 선택", ('미국 증시 (US)', '한국 증시 (Korea)'), horizontal=True)
watchlist_str = ", ".join(st.session_state.watchlist)

if market_choice == '한국 증시 (Korea)':
    presets = {
        "❤️ 내 관심종목": watchlist_str,
        "💾 반도체/HBM/유리기판 (50종)": "005930.KS, 000660.KS, 042700.KS, 000020.KS, 028300.KQ, 058470.KQ, 403870.KQ, 095340.KQ, 005290.KS, 088800.KQ, 036540.KQ, 036930.KQ, 000990.KS, 079370.KQ, 030530.KQ, 253450.KQ, 046120.KQ, 054450.KQ, 023460.KQ, 373200.KQ, 281740.KQ, 263360.KQ, 006730.KQ, 039230.KQ, 084370.KQ, 015920.KQ, 140410.KQ, 104830.KQ, 056620.KQ, 092220.KQ, 085370.KQ, 049430.KQ, 077360.KQ, 121890.KQ, 160550.KQ, 043650.KQ, 091700.KQ, 058820.KQ, 135150.KQ, 074950.KQ, 322310.KQ, 402340.KQ, 222800.KQ, 330590.KQ, 131290.KQ, 067310.KQ, 131970.KQ, 089980.KQ, 064290.KQ, 005810.KS",
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
tickers_input = st.sidebar.text_area("분석할 티커", presets[preset_key], height=150)
st.sidebar.caption(caption)
run_analysis_button = st.sidebar.button("🚀 AI 퀀트 분석 시작!", type="primary")

# --- 손절가 메뉴 (기존 v9.1 유지) ---
st.sidebar.divider()
st.sidebar.subheader("🛡️ 리스크 관리 (손절)")
stop_loss_mode = st.sidebar.radio("계산 방식", ("ATR 기반 (권장)", "피봇 지지선 (S1) 기준", "고정 비율 (%)"), horizontal=True, index=0)

atr_multiplier, stop_loss_pct = 0, 0
if stop_loss_mode == "ATR 기반 (권장)":
    atr_multiplier = st.sidebar.slider("ATR 배수 (k)", 1.0, 5.0, 2.0, 0.1)
elif stop_loss_mode == "고정 비율 (%)":
    stop_loss_pct = st.sidebar.slider("손절 비율 (%)", 1.0, 10.0, 3.0, 0.5)

# --- 4. 핵심 분석 로직 (v10.0 알고리즘 적용) ---

def analyze_dataframe(ticker, df, stop_loss_mode, market, **kwargs):
    try:
        # 1. 기술적 지표 계산 (확장됨)
        # 기본 지표
        df.ta.sma(length=20, append=True)
        df.ta.sma(length=200, append=True)
        df.ta.bbands(length=20, std=2, append=True)
        df.ta.rsi(length=14, append=True)
        df.ta.atr(length=14, append=True)
        
        # v10.0 추가 지표: 60일(수급), 120일(경기)
        df.ta.sma(length=60, append=True)
        df.ta.sma(length=120, append=True)
        
        df.dropna(inplace=True)
        if len(df) < 5: return {"티커": ticker, "신호": "데이터 부족"}

        # 컬럼 찾기 (동적 대응)
        cols = df.columns
        bbl_col = next((c for c in cols if 'BBL' in str(c)), None)
        sma200_col = next((c for c in cols if 'SMA_200' in str(c)), None)
        sma60_col = next((c for c in cols if 'SMA_60' in str(c)), None)
        sma120_col = next((c for c in cols if 'SMA_120' in str(c)), None)
        atr_col = next((c for c in cols if 'ATRr' in str(c)), None)

        if not all([bbl_col, sma200_col, sma60_col, atr_col]):
             return {"티커": ticker, "신호": "지표 생성 실패"}

        latest = df.iloc[-1]
        close = latest['close']
        currency = "₩" if market == '한국 증시 (Korea)' else "$"

        # 2. 고급 데이터 산출 (피벗, 피보나치, POC)
        p, s1, s2, r1, r2 = get_pivot_points(df)
        fib_618, fib_500, swing_high, swing_low = get_fibonacci_levels(df)
        max_vol_price = get_max_vol_price(df)

        # 3. 매수 신호 스코어링 (Confluence Logic)
        score = 0
        reasons = []
        
        # (1) 추세 필터
        trend = "상승" if close > latest[sma200_col] else "하락"
        if close > p: score += 0.5 # 피벗 중심 위에 있으면 강세 가산점
        
        # (2) 지지선 중첩 체크 (현재가 오차범위 2.5% 내)
        supports = {
            "볼린저하단": latest[bbl_col],
            "피벗 S1": s1,
            "피보나치(0.618)": fib_618,
            "60일선": latest[sma60_col],
            "120일선": latest[sma120_col],
            "최대매물대": max_vol_price
        }
        
        hit_supports = []
        for name, price in supports.items():
            if price > 0 and close <= price * 1.025 and close >= price * 0.975:
                hit_supports.append(name)
        
        if hit_supports:
            score += len(hit_supports) * 1.5 # 지지선 하나당 1.5점 가산
            reasons.extend(hit_supports)

        # (3) 과매도 필터
        rsi = latest['RSI_14']
        if rsi < 35: 
            score += 2; reasons.append(f"RSI과매도({rsi:.1f})")
        elif rsi < 45 and trend == "상승":
            score += 1

        # 4. 최종 신호 판정
        signal = "관망"
        color = "black"
        
        # 점수가 높거나, 상승장인데 지지선 2개 이상 겹칠 때
        if score >= 4 or (trend == "상승" and len(hit_supports) >= 2):
            signal = f"🔥 강력 매수"
            color = "red"
        elif score >= 2 or (trend == "상승" and len(hit_supports) >= 1):
            signal = f"✅ 매수 고려"
            color = "orange"
        elif trend == "하락" and score >= 3: # 하락장에서는 조건 엄격
            signal = f"⚠️ 반등 노림"
            color = "blue"

        if reasons: signal += f" ({', '.join(reasons)})"

        # 5. 손절가 계산 (기존 v9.1 로직 + v10.0 데이터)
        loss_info = "N/A"
        loss_val = 0
        
        if stop_loss_mode == "ATR 기반 (권장)":
            loss_val = close - (latest[atr_col] * kwargs.get('atr_multiplier', 2.0))
            loss_info = f"{currency}{loss_val:,.0f} (-{round(((close - loss_val)/close)*100, 1)}%)"
        elif stop_loss_mode == "피봇 지지선 (S1) 기준":
            if s1 > 0:
                loss_val = s1
                loss_info = f"{currency}{s1:,.0f} (피벗 S1)"
            else: loss_info = "계산 불가"
        else: # 고정 비율
            pct = kwargs.get('stop_loss_pct', 3.0)
            loss_val = close * (1 - pct/100)
            loss_info = f"{currency}{loss_val:,.0f} (-{pct}%)"

        # 6. 반환 데이터 구성
        return {
            "티커": ticker, "신호": signal, "현재가": close, "손절가": loss_info,
            "목표가": r1, "피보나치(0.618)": fib_618, "최대매물대": max_vol_price,
            "RSI": rsi, "추세": trend, "color": color
        }

    except Exception as e:
        return {"티커": ticker, "신호": "분석 오류", "오류 원인": str(e)}

# --- 5. 실행 루프 ---
if run_analysis_button:
    tickers_raw = [t.strip().upper() for t in tickers_input.split(',') if t.strip()]
    tickers = []
    for t in tickers_raw:
        if market_choice == '한국 증시 (Korea)':
            if not (t.endswith('.KS') or t.endswith('.KQ')): tickers.append(f"{t}.KS")
            else: tickers.append(t)
        else: tickers.append(t)

    if not tickers:
        st.warning("분석할 종목이 없습니다.")
    else:
        ok_results, error_results = [], []
        bar = st.progress(0, "분석 준비 중...")
        
        for i, ticker in enumerate(tickers):
            stock_name = get_stock_name(ticker)
            bar.progress((i)/len(tickers), f"[{stock_name}] 데이터 분석 중...")
            try:
                df = yf.download(ticker, period="1y", progress=False)
                if df.empty and ".KS" in ticker: 
                    retry = ticker.replace(".KS", ".KQ")
                    df = yf.download(retry, period="1y", progress=False)
                    if not df.empty: 
                        ticker, stock_name = retry, get_stock_name(retry)
                
                if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0).str.lower()
                else: df.columns = df.columns.str.lower()

                if len(df) < 60: # 60일선 계산 위해 최소 데이터 필요
                    error_results.append({"티커": ticker, "종목명": stock_name, "신호": "데이터 부족"})
                    continue

                res = analyze_dataframe(ticker, df, stop_loss_mode, market_choice, atr_multiplier=atr_multiplier, stop_loss_pct=stop_loss_pct)
                res["종목명"] = stock_name
                
                if "오류" in res.get("신호", ""): error_results.append(res)
                else: ok_results.append(res)
            except Exception as e:
                error_results.append({"티커": ticker, "종목명": stock_name, "신호": "실패", "오류 원인": str(e)})
        
        bar.empty()

        # 결과 출력
        if ok_results:
            st.success(f"✅ 분석 완료! ({len(ok_results)}개 종목)")
            res_df = pd.DataFrame(ok_results)
            
            # 정렬
            sig_map = {'🔥': 0, '✅': 1, '⚠️': 2, '관': 3}
            res_df['sort'] = res_df['신호'].apply(lambda x: sig_map.get(x[0], 9))
            res_df = res_df.sort_values('sort')
            
            # 포맷팅
            cur = "₩{:,.0f}" if market_choice == '한국 증시 (Korea)' else "${:,.2f}"
            fmt = {
                "현재가": cur, "목표가": cur, "피보나치(0.618)": cur, 
                "최대매물대": cur, "RSI": "{:.1f}"
            }
            
            # 스타일링 함수
            def color_sig(val):
                if '🔥' in val: return 'color: red; font-weight: bold'
                if '✅' in val: return 'color: orange; font-weight: bold'
                if '⚠️' in val: return 'color: blue'
                return ''

            cols = ["티커", "종목명", "신호", "현재가", "손절가", "목표가", "피보나치(0.618)", "최대매물대", "RSI", "추세"]
            st.dataframe(
                res_df[cols].style.format(fmt).map(color_sig, subset=['신호']),
                use_container_width=True, hide_index=True
            )

        if error_results:
            st.warning("⚠️ 분석 실패/제외 목록")
            st.dataframe(pd.DataFrame(error_results))

# --- 7. 관심종목 관리 (유지) ---
st.sidebar.divider()
st.sidebar.subheader("❤️ 관심종목 관리")
with st.sidebar.expander("목록 편집"):
    new_t = st.text_input("추가", placeholder="예: 005930").upper()
    if st.button("➕ 저장"):
        if new_t and new_t not in st.session_state.watchlist:
            new_l = st.session_state.watchlist + [new_t]
            if save_watchlist_to_jsonbin(new_l): st.session_state.watchlist = new_l; st.rerun()
    
    for t in st.session_state.watchlist:
        c1, c2 = st.columns([0.8, 0.2])
        c1.text(f"- {t}")
        if c2.button("X", key=f"d_{t}"):
            new_l = [x for x in st.session_state.watchlist if x != t]
            if save_watchlist_to_jsonbin(new_l): st.session_state.watchlist = new_l; st.rerun()
