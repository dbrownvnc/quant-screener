import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import requests
import numpy as np

# --- 페이지 설정 ---
st.set_page_config(page_title="Quant Screener v13.2", layout="wide")
st.title("⚡ AI 퀀트 종목 발굴기 (v13.2 장외거래 포함)")

with st.expander("📘 v13.2 업데이트: 프리/애프터마켓 반영"):
    st.markdown('''
    **1. 장외 거래(Extended Hours) 실시간 반영:**
    * 기존 정규장 종가 대신, **프리마켓/애프터마켓/주간거래**를 포함한 실시간 시세를 가져옵니다.
    * 이 실시간 가격을 기준으로 RSI, 볼린저밴드 등 모든 지표를 재계산하여 **가장 빠른 매수 신호**를 포착합니다.
    
    **2. 데이터 처리 방식:**
    * `1년치 일봉` + `실시간 5분봉(prepost=True)`을 동시에 분석하여 정확도와 속도를 모두 잡았습니다.
    ''')

# --- 1. 유틸리티 함수 ---
@st.cache_data(ttl=86400)
def get_stock_name(ticker):
    # 1. 한국 주식 (네이버 모바일 API)
    if ".KS" in ticker or ".KQ" in ticker:
        try:
            code = ticker.split('.')[0]
            url = f"https://m.stock.naver.com/api/stock/{code}/integration"
            headers = {'User-Agent': 'Mozilla/5.0'}
            res = requests.get(url, headers=headers, timeout=2)
            if res.status_code == 200:
                return res.json().get('stockName', ticker)
        except: return ticker

    # 2. 미국 주식 (yfinance)
    try:
        stock = yf.Ticker(ticker)
        return stock.info.get('shortName') or stock.info.get('longName') or ticker
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
    raw_presets = {
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
else: # 미국
    raw_presets = {
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

presets = {"-- 직접 입력 (빈 칸) --": ""}
presets.update(raw_presets)

preset_key = st.sidebar.selectbox("종목 프리셋", presets.keys())
tickers_input = st.sidebar.text_area("분석할 티커", presets[preset_key], height=150)
st.sidebar.caption(caption)
run_analysis_button = st.sidebar.button("🚀 AI 퀀트 분석 시작!", type="primary")

st.sidebar.divider()
st.sidebar.subheader("🛡️ 리스크 관리 (손절)")
stop_loss_mode = st.sidebar.radio("계산 방식", ("ATR 기반 (권장)", "피봇 지지선 (S1) 기준", "고정 비율 (%)"), horizontal=True, index=0)

atr_multiplier, stop_loss_pct = 0, 0
if stop_loss_mode == "ATR 기반 (권장)":
    atr_multiplier = st.sidebar.slider("ATR 배수 (k)", 1.0, 5.0, 2.0, 0.1)
elif stop_loss_mode == "고정 비율 (%)":
    stop_loss_pct = st.sidebar.slider("손절 비율 (%)", 1.0, 10.0, 3.0, 0.5)

# --- 4. 분석 로직 (v13.2 Real-time Extended) ---
def analyze_dataframe(ticker, df, stop_loss_mode, market, **kwargs):
    try:
        # 기술적 지표 계산
        df.ta.sma(length=20, append=True)
        df.ta.sma(length=60, append=True)
        df.ta.sma(length=120, append=True)
        df.ta.sma(length=200, append=True)
        df.ta.rsi(length=14, append=True)
        df.ta.bbands(length=20, std=2, append=True)
        df.ta.atr(length=14, append=True)
        
        df = df.dropna()
        if len(df) < 5: return {"티커": ticker, "신호": "데이터 부족"}

        cols = df.columns
        bbl_col = next((c for c in cols if 'BBL' in str(c)), None)
        bbu_col = next((c for c in cols if 'BBU' in str(c)), None)
        sma200_col = next((c for c in cols if 'SMA_200' in str(c)), None)
        sma60_col = next((c for c in cols if 'SMA_60' in str(c)), None)
        sma120_col = next((c for c in cols if 'SMA_120' in str(c)), None)
        atr_col = next((c for c in cols if 'ATRr' in str(c)), None)
        
        if not all([bbl_col, bbu_col, sma200_col, sma60_col, atr_col]):
             return {"티커": ticker, "신호": "지표 실패"}

        latest = df.iloc[-1]
        close = latest['close']
        rsi = latest['RSI_14']
        
        if ".KS" in ticker or ".KQ" in ticker: currency = "₩"
        else: currency = "$"
        
        p, s1, s2, r1, r2 = get_pivot_points(df)
        fib_618, fib_500, swing_high, swing_low = get_fibonacci_levels(df)
        max_vol_price = get_max_vol_price(df)

        # [매수 판정]
        buy_score = 0
        buy_reasons = []
        trend = "상승" if close > latest[sma200_col] else "하락"
        if close > p: buy_score += 0.5

        supports = {
            "볼린저하단": latest[bbl_col], "피벗S1": s1, "피보나치(0.618)": fib_618,
            "60일선": latest[sma60_col], "120일선": latest[sma120_col], "최대매물대": max_vol_price
        }
        hit_supports = []
        for name, price in supports.items():
            if price > 0 and close <= price * 1.025 and close >= price * 0.975:
                hit_supports.append(name)
        
        if hit_supports:
            buy_score += len(hit_supports) * 1.5
            buy_reasons.extend(hit_supports)
        
        if rsi < 35: buy_score += 2; buy_reasons.append(f"RSI과매도({rsi:.1f})")
        elif rsi < 50 and trend == "상승": buy_score += 1

        # [매도 판정]
        sell_score = 0
        sell_reasons = []
        resistances = {"볼린저상단": latest[bbu_col], "피벗R1": r1, "피벗R2": r2, "전고점": swing_high}
        hit_resistances = []
        for name, price in resistances.items():
            if price > 0 and close >= price * 0.98:
                hit_resistances.append(name)
        
        if hit_resistances:
            sell_score += len(hit_resistances) * 1.5
            sell_reasons.extend(hit_resistances)
            
        if rsi > 70: sell_score += 2; sell_reasons.append(f"RSI과매수({rsi:.1f})")
        elif rsi > 65: sell_score += 1

        # [최종 신호]
        signal = "관망"
        color = "black"

        if rsi < 60:
            if buy_score >= 5 or (trend == "상승" and len(hit_supports) >= 3):
                signal = "💎 인생 매수"
                color = "purple"
            elif buy_score >= 3.5 or (trend == "상승" and len(hit_supports) >= 2):
                signal = "🔥 강력 매수"
                color = "red"
            elif trend == "상승" and rsi < 55 and (buy_score >= 2 or len(hit_supports) >= 1):
                signal = "✅ 매수 고려"
                color = "orange"
        
        if signal == "관망":
            if sell_score >= 3 or (len(hit_resistances) >= 1 and rsi > 70):
                signal = "🚨 이익 실현"
                color = "blue"
            elif sell_score >= 1.5:
                signal = "📉 분할 매도"
                color = "skyblue"
            elif trend == "하락" and buy_score >= 3:
                signal = "⚠️ 기술적 반등"
                color = "gray"

        if signal != "관망":
            reasons = buy_reasons if "매수" in signal or "반등" in signal else sell_reasons
            if reasons: signal += f" ({', '.join(reasons)})"

        # 손절가
        loss_info = "N/A"
        if stop_loss_mode == "ATR 기반 (권장)":
            val = close - (latest[atr_col] * kwargs.get('atr_multiplier', 2.0))
            loss_info = f"{currency}{val:,.0f} (-{round((close-val)/close*100,1)}%)"
        elif stop_loss_mode == "피봇 지지선 (S1) 기준":
            loss_info = f"{currency}{s1:,.0f}" if s1>0 else "불가"
        else:
            pct = kwargs.get('stop_loss_pct', 3.0)
            val = close * (1 - pct/100)
            loss_info = f"{currency}{val:,.0f} (-{pct}%)"

        return {
            "티커": ticker, "신호": signal, "현재가": close, "손절가": loss_info,
            "목표가": r1, "피보나치(0.618)": fib_618, "RSI": rsi, "추세": trend, "color": color
        }
    except Exception as e: return {"티커": ticker, "신호": "오류", "오류 원인": str(e)}

# --- 5. 실행 루프 (이중 배치 다운로드) ---
if run_analysis_button:
    tickers_raw = [t.strip().upper() for t in tickers_input.split(',') if t.strip()]
    tickers = []
    
    for t in tickers_raw:
        if market_choice == '한국 증시 (Korea)':
            if t.endswith('.KS') or t.endswith('.KQ'): tickers.append(t)
            elif t.isdigit(): tickers.append(f"{t}.KS")
            else: tickers.append(t)
        else: tickers.append(t)

    if not tickers: st.warning("분석할 종목을 입력해주세요.")
    else:
        results, errors = [], []
        status_text = st.empty()
        status_text.text("데이터 다운로드 중... (1/2: Daily History)")
        
        try:
            # 1. 일봉 데이터 (지표 계산용) - 1년
            batch_data = yf.download(tickers, period="1y", group_by='ticker', progress=False)
            
            status_text.text("데이터 다운로드 중... (2/2: Real-time Extended)")
            
            # 2. 실시간 데이터 (프리/애프터장 포함) - 5일, 5분봉
            batch_rt = yf.download(tickers, period="5d", interval="5m", prepost=True, group_by='ticker', progress=False)
            
            bar = st.progress(0, "분석 시작...")
            
            for i, ticker in enumerate(tickers):
                status_text.text(f"[{ticker}] 분석 중... ({i+1}/{len(tickers)})")
                bar.progress((i+1)/len(tickers))
                
                try:
                    # Data A: Daily
                    if len(tickers) == 1: df = batch_data.copy()
                    else:
                        try: df = batch_data[ticker].copy()
                        except KeyError: 
                            if ".KS" in ticker: # 코스닥 재시도
                                alt = ticker.replace(".KS", ".KQ")
                                df = yf.download(alt, period="1y", progress=False)
                                if not df.empty: ticker = alt
                            else: df = pd.DataFrame()

                    if df.empty:
                        errors.append({"티커": ticker, "신호": "데이터 없음"})
                        continue
                    
                    df.columns = df.columns.str.lower()

                    # Data B: Real-time Extended (장외 포함 최신가 덮어쓰기)
                    try:
                        if len(tickers) == 1: df_rt = batch_rt
                        else: df_rt = batch_rt[ticker]
                        
                        if not df_rt.empty:
                            # 5분봉의 가장 마지막 종가 = 현재가 (장외 포함)
                            current_price = df_rt['Close'].iloc[-1]
                            if pd.notna(current_price):
                                # 일봉 데이터의 마지막 row 종가를 실시간 가격으로 업데이트
                                # (이렇게 해야 RSI, 볼린저밴드가 현재가 기준으로 다시 계산됨)
                                df.iloc[-1, df.columns.get_loc('close')] = current_price
                    except: pass # RT 데이터 없으면 그냥 종가 사용

                    # 분석 실행
                    res = analyze_dataframe(ticker, df, stop_loss_mode, market_choice, atr_multiplier=atr_multiplier, stop_loss_pct=stop_loss_pct)
                    res["종목명"] = get_stock_name(ticker)
                    
                    if "오류" in res.get("신호", ""): errors.append(res)
                    else: results.append(res)
                    
                except Exception as e:
                    errors.append({"티커": ticker, "신호": "분석 실패", "원인": str(e)})

            bar.empty()
            status_text.empty()

            if results:
                st.success(f"✅ 분석 완료! ({len(results)}건 - 장외거래 반영됨)")
                res_df = pd.DataFrame(results)
                sig_map = {'💎':0, '🔥':1, '✅':2, '⚠️':3, '🚨':4, '📉':5, '관':6}
                res_df['sort'] = res_df['신호'].apply(lambda x: sig_map.get(x[0], 9))
                res_df = res_df.sort_values('sort')

                cur = "₩{:,.0f}" if market_choice == '한국 증시 (Korea)' else "${:,.2f}"
                fmt = {"현재가": cur, "목표가": cur, "피보나치(0.618)": cur, "RSI": "{:.1f}"}
                def color_sig(val):
                    if '💎' in val: return 'color: purple; font-weight: bold; background-color: #f0f0f5'
                    if '🔥' in val: return 'color: red; font-weight: bold'
                    if '✅' in val: return 'color: orange; font-weight: bold'
                    if '🚨' in val: return 'color: blue; font-weight: bold'
                    if '📉' in val: return 'color: skyblue; font-weight: bold'
                    if '⚠️' in val: return 'color: gray'
                    return ''

                cols = ["티커", "종목명", "신호", "현재가", "손절가", "목표가", "피보나치(0.618)", "RSI", "추세"]
                st.dataframe(res_df[cols].style.format(fmt).map(color_sig, subset=['신호']), use_container_width=True, hide_index=True)

            if errors: st.warning("⚠️ 실패 목록"); st.dataframe(pd.DataFrame(errors))

        except Exception as e:
            st.error(f"다운로드 중 오류 발생: {e}")

# --- 6. 관심종목 관리 ---
st.sidebar.divider()
st.sidebar.subheader("❤️ 관심종목 관리")
with st.sidebar.expander("목록 편집"):
    new_t = st.text_input("추가", placeholder="예: 005930").upper()
    if st.button("➕ 저장"):
        if new_t and new_t not in st.session_state.watchlist:
            new_l = st.session_state.watchlist + [new_t]
            if save_watchlist(new_l): st.session_state.watchlist = new_l; st.rerun()
    for t in st.session_state.watchlist:
        c1, c2 = st.columns([0.8, 0.2])
        c1.text(f"- {t}")
        if c2.button("X", key=f"d_{t}"):
            new_l = [x for x in st.session_state.watchlist if x != t]
            if save_watchlist(new_l): st.session_state.watchlist = new_l; st.rerun()
