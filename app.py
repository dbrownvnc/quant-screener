import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import requests
import json
import re

# --- 페이지 설정 ---
st.set_page_config(page_title="Quant Screener v9.1", layout="wide")

st.title("📈 AI 퀀트 종목 발굴기 (v9.1 - 통합 프리셋 적용)")

with st.expander("✨ 앱 소개 및 v9.1 특징"):
    st.markdown('''
    **AI 퀀트 종목 발굴기는 기술적 분석 지표를 종합하여 매수 타이밍에 근접한 종목을 찾아냅니다.**

    **핵심 로직:**
    1.  **추세 필터:** 200일 이동평균선(SMA200) 위에 있는 '상승 추세' 종목 우선
    2.  **정교한 진입:** 볼린저밴드 하단, RSI 과매도, 피봇 지지선(S1) 중첩 구간 포착
    3.  **거래량 분석:** 평소 대비 거래량 급증(수급 유입) 포착
    4.  **리스크 관리:** ATR 기반 또는 지지선 이탈 시 자동 손절가 계산
    ''')

# --- 1. 유틸리티 함수 ---

@st.cache_data(ttl=86400)
def get_stock_name(ticker):
    # 한국 종목명 매핑 보정
    hotfix_map = {
        "005930.KS": "삼성전자", "000660.KS": "SK하이닉스",
        "373220.KS": "LG에너지솔루션", "373220.KQ": "LG에너지솔루션"
    }
    if ticker.upper() in hotfix_map:
        return hotfix_map[ticker.upper()]
    
    # 네이버 금융 크롤링 (한국)
    try:
        if ".KS" in ticker or ".KQ" in ticker:
            code = ticker.split(".")[0]
            url = f"https://ac.finance.naver.com/ac?q={code}&q_enc=euc-kr&t_opts=2"
            response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=3)
            items = response.json().get('items', [])
            if items and items[0]:
                for item in items[0]:
                    if isinstance(item, list) and len(item) > 1 and item[0] == code:
                        return item[1]
    except Exception: pass
    
    # yfinance (미국/기타)
    try:
        stock = yf.Ticker(ticker)
        name = stock.info.get('longName') or stock.info.get('shortName')
        if name: return name
    except Exception: pass
    return ticker

def get_pivot_points(df):
    """피봇 포인트 (전일 고가/저가/종가 기준) 계산"""
    if len(df) < 2: return 0, 0, 0
    last = df.iloc[-2] # 전일 데이터 사용
    high, low, close = last['high'], last['low'], last['close']
    pivot = (high + low + close) / 3
    s1 = (2 * pivot) - high
    r1 = (2 * pivot) - low
    s2 = pivot - (high - low)
    return s1, r1, s2

# --- 2. 데이터 저장소 (JSONBin.io) 설정 ---
# secrets.toml에 설정된 키가 없으면 로컬 리스트만 사용하도록 예외처리 가능하지만,
# 여기서는 사용자 코드를 존중하여 secrets 사용을 전제로 함.
api_key_names = ["JSONBIN_API_KEY", "jsonbin_api_key"]
bin_id_names = ["JSONBIN_BIN_ID", "jsonbin_bin_id"]
JSONBIN_API_KEY = next((st.secrets.get(key) for key in api_key_names), None)
JSONBIN_BIN_ID = next((st.secrets.get(key) for key in bin_id_names), None)

if not JSONBIN_API_KEY or not JSONBIN_BIN_ID:
    st.warning("⚠️ [Secrets 미설정] 관심종목 저장 기능이 비활성화됩니다. `.streamlit/secrets.toml`을 확인하세요.")
    JSONBIN_URL = None
else:
    JSONBIN_URL = f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}"
    HEADERS = {'Content-Type': 'application/json', 'X-Master-Key': JSONBIN_API_KEY}

@st.cache_data(ttl=300)
def load_watchlist_from_jsonbin():
    if not JSONBIN_URL: return []
    try:
        response = requests.get(f"{JSONBIN_URL}/latest", headers=HEADERS)
        response.raise_for_status()
        return response.json().get('record', {}).get('watchlist', [])
    except Exception: return []

def save_watchlist_to_jsonbin(watchlist_data):
    if not JSONBIN_URL: return False
    try:
        requests.put(JSONBIN_URL, headers=HEADERS, json={'watchlist': watchlist_data}).raise_for_status()
        st.cache_data.clear()
        return True
    except Exception: return False

# --- 3. 세션 상태 초기화 ---
if 'watchlist_loaded' not in st.session_state:
    st.session_state.watchlist = load_watchlist_from_jsonbin()
    st.session_state.watchlist_loaded = True


# --- 4. 사이드바 UI (프리셋 업데이트됨) ---
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

st.sidebar.divider()
st.sidebar.subheader("🛡️ 리스크 관리 (손절)")
stop_loss_mode = st.sidebar.radio("계산 방식", ("ATR 기반 (권장)", "피봇 지지선 (S1) 기준", "고정 비율 (%)"), horizontal=True, index=0)

atr_multiplier, stop_loss_pct = 0, 0
if stop_loss_mode == "ATR 기반 (권장)":
    atr_multiplier = st.sidebar.slider("ATR 배수 (k)", 1.0, 5.0, 2.0, 0.1)
elif stop_loss_mode == "고정 비율 (%)":
    stop_loss_pct = st.sidebar.slider("손절 비율 (%)", 1.0, 10.0, 3.0, 0.5)

# --- 5. 분석 로직 (Core) ---

def analyze_dataframe(ticker, df, stop_loss_mode, market, **kwargs):
    try:
        # 1. 지표 계산
        df.ta.sma(length=200, append=True)
        df.ta.rsi(length=14, append=True)
        df.ta.bbands(length=20, std=2, append=True)
        df.ta.atr(length=14, append=True)
        df.dropna(inplace=True)
        
        # 데이터가 너무 적으면 분석 불가
        if df.empty or len(df) < 5: return {"티커": ticker, "신호": "데이터 부족"}

        cols = df.columns
        bbl_col = next((c for c in cols if 'BBL' in str(c)), None)
        sma_col = next((c for c in cols if 'SMA_200' in str(c)), None)
        atr_col = next((c for c in cols if 'ATRr' in str(c)), None)
        
        if not all([bbl_col, sma_col, atr_col]): 
            return {"티커": ticker, "신호": "지표 생성 실패"}

        latest = df.iloc[-1]
        close = latest['close']
        currency = "₩" if market == '한국 증시 (Korea)' else "$"

        # 2. 지지/저항 레벨 산출 (피벗)
        s1, r1, s2 = get_pivot_points(df)
        swing_low_20d = df['low'].tail(20).min()

        # 3. 지지선 붕괴 감지 (UI 표시용)
        support_display = f"{currency}{s1:,.0f}" if s1 > 0 else "N/A"
        if s1 > 0 and close < s1:
            support_display = f"{currency}{s2:,.0f} (S1 붕괴⚠️)"

        # 4. 신호 로직 (스코어링)
        score, reasons = 0, []
        
        # A. 볼린저 밴드 하단 (과매도)
        if close <= latest[bbl_col] * 1.01:
            score += 1; reasons.append("볼린저 하단")
            
        # B. 피봇 지지 (붕괴되지 않은 상태에서 근접)
        if s1 > 0 and close <= s1 * 1.02 and close >= s1 * 0.98:
            score += 1; reasons.append("피봇 지지")
            
        # C. 전저점 지지
        if close <= swing_low_20d * 1.03 and close >= swing_low_20d * 0.98:
            score += 1; reasons.append("전저점 근접")
        
        # D. RSI 과매도
        rsi = latest['RSI_14']
        if rsi < 35: score += 1
        
        # E. 추세 판단 (200일선)
        trend = "상승" if close > latest[sma_col] else "하락"
        
        # 최종 신호 결정
        signal = "관망"
        if trend == "상승": # 상승 추세일 때만 매수 고려
            if score >= 2:
                signal = f"🔥 강력 매수 ({', '.join(reasons)})" if reasons else "🔥 강력 매수"
            elif score == 1 and rsi < 45:
                signal = f"✅ 매수 고려 ({reasons[0]})" if reasons else "✅ 매수 고려"
        elif trend == "하락":
             if score >= 2 and rsi < 30: # 하락장에서는 매우 보수적으로 (과매도 심화 시)
                 signal = f"⚠️ 기술적 반등 노림 ({', '.join(reasons)})"

        # 5. 거래량 필터
        vol_signal = "보통"
        if 'volume' in df.columns and len(df) > 20:
            vol_avg_20 = df['volume'].rolling(20).mean().iloc[-1]
            if vol_avg_20 > 0 and latest['volume'] > vol_avg_20 * 1.5:
                vol_signal = "⬆️ 양봉 급증" if close > latest['open'] else "⬇️ 음봉 급증"

        # 6. 손절가 계산
        loss_info = "N/A"
        if stop_loss_mode == "ATR 기반 (권장)":
            loss_price = close - (latest[atr_col] * kwargs.get('atr_multiplier', 2.0))
            loss_info = f"{currency}{loss_price:,.0f} (-{round(((close - loss_price) / close) * 100, 1)}%)"
        elif stop_loss_mode == "피봇 지지선 (S1) 기준":
            if s1 > 0: 
                loss_info = f"{currency}{s1:,.0f} (피봇 S1)"
            else: 
                loss_info = "계산 불가"
        else: # 고정 비율
            loss_price = close * (1 - kwargs.get('stop_loss_pct', 3.0) / 100)
            loss_info = f"{currency}{loss_price:,.0f} (-{kwargs.get('stop_loss_pct', 3.0)}%)"

        return {
            "티커": ticker, "신호": signal, "현재가": close, "손절가": loss_info,
            "지지(S1)": support_display, "저항(R1)": r1, "RSI": rsi, 
            "추세": trend, "거래량": vol_signal
        }
    except Exception as e:
        return {"티커": ticker, "신호": "분석 오류", "오류 원인": str(e)}


# --- 6. 실행 루프 ---
if run_analysis_button:
    tickers_raw = [t.strip().upper() for t in tickers_input.split(',') if t.strip()]
    
    # 한국 주식 티커 보정 (숫자로만 입력 시 .KS 붙임)
    tickers = []
    for t in tickers_raw:
        if market_choice == '한국 증시 (Korea)':
            # 이미 .KS나 .KQ가 있으면 그대로, 없으면 기본적으로 .KS 붙임
            if not (t.endswith('.KS') or t.endswith('.KQ')):
                 tickers.append(f"{t}.KS")
            else:
                 tickers.append(t)
        else:
             tickers.append(t)

    if not tickers:
        st.warning("분석할 종목이 없습니다.")
    else:
        ok_results, error_results = [], []
        bar = st.progress(0, "분석 준비 중...")
        
        for i, ticker in enumerate(tickers):
            stock_name = get_stock_name(ticker)
            bar.progress((i)/len(tickers), f"[{stock_name}] 데이터 분석 중...")
            try:
                # 데이터 다운로드
                df = yf.download(ticker, period="1y", progress=False)
                
                # 코스피 데이터가 비어있다면 코스닥(.KQ)으로 재시도
                if df.empty and ".KS" in ticker: 
                    retry_ticker = ticker.replace(".KS", ".KQ")
                    df_kq = yf.download(retry_ticker, period="1y", progress=False)
                    if not df_kq.empty:
                        df, ticker, stock_name = df_kq, retry_ticker, get_stock_name(retry_ticker)
                
                # 컬럼명 소문자 변환 (멀티인덱스 대응)
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0).str.lower()
                else:
                    df.columns = df.columns.str.lower()

                if df.empty or len(df) < 100:
                    error_results.append({"티커": ticker, "종목명": stock_name, "신호": "데이터 부족"})
                    continue

                res = analyze_dataframe(ticker, df, stop_loss_mode, market_choice, atr_multiplier=atr_multiplier, stop_loss_pct=stop_loss_pct)
                res["종목명"] = stock_name
                
                if "오류" in res.get("신호", ""): 
                    error_results.append(res)
                else: 
                    ok_results.append(res)
                    
            except Exception as e:
                error_results.append({"티커": ticker, "종목명": stock_name, "신호": "실패", "오류 원인": str(e)})
        
        bar.empty()

        # --- 결과 출력 ---
        if ok_results:
            st.success(f"✅ 분석 완료! ({len(ok_results)}개 종목)")
            res_df = pd.DataFrame(ok_results)
            
            # 정렬 우선순위: 강력 매수 -> 매수 고려 -> 반등 노림 -> 관망
            signal_order = {'🔥': 0, '✅': 1, '⚠': 2, '관': 3}
            res_df['sort_key'] = res_df['신호'].apply(lambda x: signal_order.get(x[0], 99))
            res_df = res_df.sort_values(by='sort_key')
            
            # 포맷팅
            currency_format = "₩{:,.0f}" if market_choice == '한국 증시 (Korea)' else "${:,.2f}"
            cols = ["티커", "종목명", "신호", "현재가", "손절가", "지지(S1)", "저항(R1)", "RSI", "거래량", "추세"]
            final_df = res_df[[c for c in cols if c in res_df.columns]]
            
            styler = final_df.style.format({
                "현재가": currency_format, 
                "저항(R1)": currency_format, 
                "RSI": "{:.1f}"
            })
            # 스타일링: 중앙 정렬 및 가독성
            styler.set_properties(**{'font-size': '13px', 'text-align': 'center'})
            styler.set_table_styles([{'selector': 'th', 'props': [('font-size', '13px'), ('text-align', 'center')]}])
            
            st.dataframe(styler, use_container_width=True, hide_index=True)

        if error_results:
            st.warning("⚠️ 분석 실패/제외 목록")
            st.dataframe(pd.DataFrame(error_results), hide_index=True)

# --- 7. 관심종목 관리 (하단) ---
st.sidebar.divider()
st.sidebar.subheader("❤️ 관심종목 관리")
with st.sidebar.expander("목록 편집"):
    new_t = st.text_input("추가", placeholder="예: 005930").upper()
    if st.button("➕ 저장"):
        if new_t and new_t not in st.session_state.watchlist:
            new_l = st.session_state.watchlist + [new_t]
            if save_watchlist_to_jsonbin(new_l):
                st.session_state.watchlist = new_l; st.rerun()
    
    # 목록 삭제 버튼
    for t in st.session_state.watchlist:
        c1, c2 = st.columns([0.8, 0.2])
        c1.text(f"- {t}")
        if c2.button("X", key=f"d_{t}"):
            new_l = [x for x in st.session_state.watchlist if x != t]
            if save_watchlist_to_jsonbin(new_l):
                st.session_state.watchlist = new_l; st.rerun()
