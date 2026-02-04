import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import requests
import numpy as np

# --- 페이지 설정 ---
st.set_page_config(page_title="Quant Screener v10.0 (Final)", layout="wide")
st.title("💎 AI 퀀트 종목 발굴기 (v10.0 Final)")

with st.expander("📘 v10.0 알고리즘 이론 설명 (Confluence Logic)"):
    st.markdown('''
    **이 툴은 '지지선의 중첩(Confluence)'을 찾아냅니다. 하나의 지표보다 여러 지표가 겹칠 때 신뢰도가 급상승합니다.**
    
    1.  **피보나치 되돌림 (Fibonacci):** 최근 120일(6개월) 고점/저점 기준 **0.618(황금비율)** 구간을 계산합니다.
    2.  **스마트 매물대 (POC Proxy):** 최근 1년 중 **가장 많은 거래량이 터진 날의 종가**를 강력한 지지/저항으로 간주합니다.
    3.  **이동평균선 확장:** 20일(단기)뿐만 아니라 **60일(수급선), 120일(경기선)** 지지 여부를 체크합니다.
    4.  **피벗 포인트 (Pivot):** 당일 주가가 **피벗 중심(P)** 위에 있는지 확인하여 추세 힘을 측정합니다.
    ''')

# --- 1. 유틸리티 함수 ---

@st.cache_data(ttl=86400)
def get_stock_name(ticker):
    # 한국 종목명 매핑
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
    """피벗 포인트 (P, S1, S2, R1, R2) 계산"""
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
    """최근 N일 고점/저점 기준 피보나치 레벨 계산"""
    if len(df) < period: period = len(df)
    recent_data = df[-period:]
    max_h = recent_data['high'].max()
    min_l = recent_data['low'].min()
    diff = max_h - min_l
    
    fib_0618 = max_h - (diff * 0.618) # 황금비율 지지선
    fib_0500 = max_h - (diff * 0.5)   # 절반 되돌림
    return fib_0618, fib_0500, max_h, min_l

def get_max_vol_price(df, period=240):
    """최근 N일 중 최대 거래량이 터진 날의 종가 (세력 평단 추정)"""
    if len(df) < period: period = len(df)
    recent_data = df[-period:]
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

# --- 3. 사이드바 UI (통합 프리셋) ---
market_choice = st.sidebar.radio("시장 선택", ('미국 증시 (US)', '한국 증시 (Korea)'), horizontal=True)
watchlist_str = ", ".join(st.session_state.watchlist)

if market_choice == '한국 증시 (Korea)':
    presets = {
        "❤️ 내 관심종목": watchlist_str,
        "💾 반도체/HBM (대장주)": "005930.KS, 000660.KS, 042700.KS, 000020.KS, 028300.KQ, 058470.KQ, 403870.KQ, 095340.KQ, 005290.KS",
        "🔋 2차전지/에코프로": "373220.KS, 006400.KS, 051910.KS, 003670.KS, 247540.KQ, 086520.KQ, 066970.KQ, 005070.KS, 277810.KQ",
        "🤖 로봇/AI/플랫폼": "035420.KS, 035720.KS, 251270.KS, 036570.KQ, 005940.KS, 293490.KQ, 006360.KS, 352820.KS",
        "🛡️ 방산/조선/전력": "012450.KS, 064350.KS, 079550.KS, 042660.KS, 010140.KS, 267250.KS, 024110.KS, 010120.KS, 000720.KS",
        "💊 바이오/셀트리온": "207940.KS, 068270.KS, 196170.KQ, 000100.KS, 326030.KQ, 214150.KQ, 000250.KS, 028300.KQ",
        "💄 화장품/푸드": "271560.KS, 192820.KS, 243070.KS, 097950.KS, 003230.KS, 280360.KS, 090430.KS, 278470.KS",
        "🏦 금융/저PBR": "105560.KS, 055550.KS, 086790.KS, 032830.KS, 316140.KS, 000810.KS, 138040.KS"
    }
    caption = "💡 코드 입력 (예: 005930)"
else:
    presets = {
        "❤️ 내 관심종목": watchlist_str,
        "👑 M7 & 빅테크": "NVDA, AAPL, MSFT, GOOGL, AMZN, META, TSLA, NFLX, AVGO, AMD, ORCL, CRM",
        "💾 반도체/AI": "INTC, QCOM, TSM, MU, ARM, SMCI, DELL, AMAT, LRCX, ASML, MRVL, ON",
        "☁️ 소프트웨어/보안": "PLTR, SNOW, CRWD, PANW, FTNT, MDB, DDOG, NET, NOW, ADSK, U, SQ",
        "💊 헬스케어/비만": "LLY, NVO, VRTX, REGN, AMGN, PFE, MRK, JNJ, UNH, ABBV",
        "💰 핀테크/코인": "JPM, V, MA, PYPL, COIN, HOOD, MSTR, MARA, CLSK, SOFI, NU",
        "🛡️ 방산/우주/에너지": "LMT, RTX, GD, BA, NOC, PL, GE, XOM, CVX, NEE, VST, CEG",
        "📈 3배 레버리지 ETF": "TQQQ, SQQQ, SOXL, SOXS, FNGU, BULZ, NVDL, TSLL, CONL"
    }
    caption = "💡 티커 입력 (예: NVDA)"

preset_key = st.sidebar.selectbox("종목 프리셋", presets.keys())
tickers_input = st.sidebar.text_area("분석할 티커", presets[preset_key], height=120)
st.sidebar.caption(caption)
run_btn = st.sidebar.button("🚀 AI 퀀트 분석 시작", type="primary")

st.sidebar.divider()
st.sidebar.subheader("🛡️ 설정")
stop_loss_pct = st.sidebar.slider("손절가 비율 (%)", 1.0, 10.0, 3.0, 0.5)

# --- 4. 핵심 분석 로직 (v10.0) ---

def analyze_stock(ticker, df, market, stop_pct):
    try:
        # 1. 지표 계산
        df.ta.sma(length=20, append=True)
        df.ta.sma(length=60, append=True)  # 수급선 (신규)
        df.ta.sma(length=120, append=True) # 경기선 (신규)
        df.ta.sma(length=200, append=True) # 추세선
        df.ta.rsi(length=14, append=True)
        df.ta.bbands(length=20, std=2, append=True)
        
        df.dropna(inplace=True)
        if len(df) < 5: return None

        latest = df.iloc[-1]
        close = latest['close']
        
        # 2. 고급 지표 산출
        p, s1, s2, r1, r2 = get_pivot_points(df) # 피벗
        fib_618, fib_500, swing_high, swing_low = get_fibonacci_levels(df) # 피보나치
        max_vol_price = get_max_vol_price(df) # 대량 거래 매물대 (POC Proxy)

        # 3. 매수 신호 스코어링 (Confluence)
        score = 0
        reasons = []
        
        # (1) 추세 필터
        trend = "상승" if close > latest['SMA_200'] else "하락"
        if close > p: score += 0.5 # 피벗 중심 위에 있으면 강세 가산점
        
        # (2) 지지선 중첩 체크 (오차범위 2% 내)
        supports = {
            "볼린저하단": latest['BBL_20_2.0'],
            "피벗 S1": s1,
            "피벗 S2": s2,
            "피보나치(0.618)": fib_618,
            "60일선": latest['SMA_60'],
            "120일선": latest['SMA_120'],
            "최대매물대": max_vol_price
        }
        
        hit_supports = []
        for name, price in supports.items():
            if price > 0 and close <= price * 1.025 and close >= price * 0.97:
                hit_supports.append(name)
        
        if hit_supports:
            score += len(hit_supports) * 1.5 # 지지선 하나당 1.5점
            reasons.extend(hit_supports)

        # (3) 과매도 필터 (RSI)
        rsi = latest['RSI_14']
        if rsi < 35: 
            score += 2
            reasons.append(f"RSI과매도({rsi:.1f})")
        elif rsi < 45 and trend == "상승":
            score += 1
            reasons.append("건전한조정")
            
        # 4. 최종 신호 판정
        signal = "관망"
        color = "black"
        
        if score >= 4 or (trend == "상승" and score >= 3):
            signal = f"🔥 강력 매수"
            color = "red"
        elif score >= 2:
            signal = f"✅ 매수 고려"
            color = "orange"
        elif trend == "상승" and len(hit_supports) >= 1:
            signal = "👀 눌림목 관찰"
            color = "blue"

        if reasons: signal += f" ({', '.join(reasons)})"

        # 5. 목표가 및 손절가
        target_price = r1 if r1 > close else swing_high # 1차 목표는 피벗 R1 혹은 전고점
        loss_price = close * (1 - stop_pct/100)
        
        # 지지선이 바로 밑에 있다면 손절가를 그 아래로 조정 (Smart Stop Loss)
        nearest_support = max([v for v in supports.values() if v < close], default=0)
        if nearest_support > 0 and (close - nearest_support)/close < 0.05:
            loss_price = nearest_support * 0.99 # 지지선 1% 아래로 설정

        currency = "₩" if market == '한국 증시 (Korea)' else "$"
        
        return {
            "티커": ticker,
            "신호": signal,
            "현재가": close,
            "목표가(R1/고점)": target_price,
            "손절가": loss_price,
            "피보나치(0.618)": fib_618,
            "최대매물대": max_vol_price,
            "추세": trend,
            "RSI": rsi,
            "color": color
        }

    except Exception as e: return {"티커": ticker, "신호": "오류", "오류내용": str(e)}

# --- 5. 실행 루프 ---
if run_btn:
    tickers_raw = [t.strip().upper() for t in tickers_input.split(',') if t.strip()]
    tickers = []
    for t in tickers_raw:
        if market_choice == '한국 증시 (Korea)' and not (t.endswith('.KS') or t.endswith('.KQ')):
             tickers.append(f"{t}.KS")
        else: tickers.append(t)

    if not tickers: st.warning("종목을 입력해주세요.")
    else:
        results, errors = [], []
        bar = st.progress(0, "분석 시작...")
        
        for i, ticker in enumerate(tickers):
            name = get_stock_name(ticker)
            bar.progress((i)/len(tickers), f"[{name}] 분석 중...")
            try:
                df = yf.download(ticker, period="1y", progress=False)
                if df.empty and ".KS" in ticker: # 코스닥 재시도
                    retry = ticker.replace(".KS", ".KQ")
                    df = yf.download(retry, period="1y", progress=False)
                    if not df.empty: ticker, name = retry, get_stock_name(retry)

                # 컬럼 소문자화
                if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0).str.lower()
                else: df.columns = df.columns.str.lower()

                res = analyze_stock(ticker, df, market_choice, stop_loss_pct)
                if res:
                    res['종목명'] = name
                    if "오류" in res['신호']: errors.append(res)
                    else: results.append(res)
                else: errors.append({"티커": ticker, "종목명": name, "신호": "데이터 부족"})
            except Exception as e: errors.append({"티커": ticker, "신호": "실패", "오류내용": str(e)})
        
        bar.empty()

        # 결과 출력
        if results:
            st.success(f"✅ 분석 완료! ({len(results)}건)")
            df_res = pd.DataFrame(results)
            
            # 정렬 (강력 매수 상단)
            sig_map = {'🔥':0, '✅':1, '👀':2, '관':3}
            df_res['sort'] = df_res['신호'].apply(lambda x: sig_map.get(x[0], 9))
            df_res = df_res.sort_values('sort')
            
            # 테이블 서식
            cur = "₩{:,.0f}" if market_choice == '한국 증시 (Korea)' else "${:,.2f}"
            fmt = {
                "현재가": cur, "목표가(R1/고점)": cur, "손절가": cur,
                "피보나치(0.618)": cur, "최대매물대": cur, "RSI": "{:.1f}"
            }
            
            # 스타일링
            def color_sig(val):
                if '🔥' in val: return 'color: red; font-weight: bold'
                if '✅' in val: return 'color: orange; font-weight: bold'
                if '👀' in val: return 'color: blue'
                return ''

            cols = ["티커", "종목명", "신호", "현재가", "목표가(R1/고점)", "손절가", "피보나치(0.618)", "최대매물대", "RSI", "추세"]
            st.dataframe(
                df_res[cols].style.format(fmt).map(color_sig, subset=['신호']),
                use_container_width=True, hide_index=True
            )

        if errors:
            st.warning("⚠️ 분석 실패 목록")
            st.dataframe(pd.DataFrame(errors))

# --- 하단: 관심종목 관리 ---
with st.sidebar.expander("❤️ 관심종목 편집"):
    new_t = st.text_input("추가", placeholder="TICKER").upper()
    if st.button("➕ 추가"):
        if new_t and new_t not in st.session_state.watchlist:
            save_watchlist(st.session_state.watchlist + [new_t])
            st.rerun()
    for t in st.session_state.watchlist:
        c1, c2 = st.columns([0.8, 0.2])
        c1.text(t)
        if c2.button("X", key=t):
            save_watchlist([x for x in st.session_state.watchlist if x != t])
            st.rerun()
