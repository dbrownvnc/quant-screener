import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import requests
import json
import re

# --- 페이지 설정 ---
st.set_page_config(page_title="Pro Quant Screener", layout="wide")

st.title("📈 AI 프로 퀀트 스크리너 (v9.0 - 지지/저항 완벽 분석)")

with st.expander("✨ v9.0 업그레이드 내용 (필독)"):
    st.markdown('''
    **v9.0은 기존 로직에 '구조적 지지/저항' 이론을 결합했습니다.**

    1.  **📊 피봇(Pivot) 지지/저항:** 전일의 고가, 저가, 종가를 바탕으로 **수학적인 1차 저항선(목표가)과 지지선**을 계산합니다.
    2.  **🏆 종합 스코어링:** 추세, 모멘텀, 거래량, 위치를 종합하여 **100점 만점**으로 종목의 매력도를 평가합니다.
    3.  **🎯 명확한 목표가:** 막연한 매수가 아닌, **손절가(ATR)**와 **목표가(저항선)**를 동시에 제시하여 손익비(Risk/Reward)를 보여줍니다.
    ''')

# --- 종목명 가져오기 (v8.5 로직 유지) ---
@st.cache_data(ttl=86400)
def get_stock_name(ticker):
    hotfix_map = {"005930.KS": "삼성전자", "000660.KS": "SK하이닉스", "373220.KS": "LG에너지솔루션"}
    if ticker.upper() in hotfix_map: return hotfix_map[ticker.upper()]
    
    if ticker.upper().endswith(('.KS', '.KQ')):
        try:
            code = ticker.split('.')[0]
            url = f"https://ac.finance.naver.com/ac?q={code}&q_enc=euc-kr&t_opts=2"
            response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=2)
            items = response.json().get('items', [])
            if items and items[0]:
                 for item in items[0]:
                    if item[0] == code: return item[1]
        except: pass
    
    try:
        stock = yf.Ticker(ticker)
        return stock.info.get('shortName') or stock.info.get('longName') or ticker
    except: return ticker

# --- JSONBin 설정 (기존 유지) ---
api_key_names = ["JSONBIN_API_KEY", "jsonbin_api_key"]
bin_id_names = ["JSONBIN_BIN_ID", "jsonbin_bin_id"]
JSONBIN_API_KEY = next((st.secrets.get(key) for key in api_key_names), None)
JSONBIN_BIN_ID = next((st.secrets.get(key) for key in bin_id_names), None)
JSONBIN_URL = f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}"
HEADERS = {'Content-Type': 'application/json', 'X-Master-Key': JSONBIN_API_KEY}

@st.cache_data(ttl=300)
def load_watchlist():
    try: return requests.get(f"{JSONBIN_URL}/latest", headers=HEADERS).json()['record'].get('watchlist', [])
    except: return []

def save_watchlist(data):
    try: 
        requests.put(JSONBIN_URL, headers=HEADERS, json={'watchlist': data})
        st.cache_data.clear()
        return True
    except: return False

if 'watchlist_loaded' not in st.session_state:
    st.session_state.watchlist = load_watchlist()
    st.session_state.watchlist_loaded = True

# --- UI 설정 ---
market_choice = st.sidebar.radio("시장 선택", ('미국 증시 (US)', '한국 증시 (Korea)'), horizontal=True)
watchlist_str = ", ".join(st.session_state.watchlist)

if market_choice == '한국 증시 (Korea)':
    presets = {
        "❤️ 내 관심종목": watchlist_str,
        "💾 반도체/HBM": "005930,000660,042700,000020,028300.KQ,058470.KQ",
        "🔋 2차전지": "373220,006400,051910,247540.KQ,086520.KQ",
        "💉 바이오": "207940,068270,196170.KQ,000100,214150.KQ",
        "⚡ 전력/원전": "267250,024110,010120,000720,034020",
        "🚗 자동차/방산": "005380,000270,012450,064350,042660"
    }
else:
    presets = {
        "❤️ 내 관심종목": watchlist_str,
        "👑 빅테크 (Mag 7)": "NVDA,AAPL,MSFT,GOOGL,AMZN,META,TSLA",
        "🤖 AI/반도체": "AMD,AVGO,TSM,MU,INTC,ARM,SMCI,PLTR",
        "💰 비트코인/금융": "MSTR,COIN,HOOD,JPM,V,MA",
        "💊 헬스케어": "LLY,NVO,UNH,JNJ,PFE",
        "📈 3배 레버리지": "TQQQ,SOXL,FNGU,NVDL"
    }

preset_key = st.sidebar.selectbox("종목 프리셋", presets.keys())
tickers_input = st.sidebar.text_area("분석 티커", presets[preset_key], height=80)
st.sidebar.caption("💡 팁: 코스닥 종목은 .KQ를 붙이면 속도가 훨씬 빠릅니다 (예: 247540.KQ)")

stop_loss_k = st.sidebar.slider("ATR 손절 배수 (k)", 1.5, 4.0, 2.5, 0.1, help="높을수록 손절 라인이 여유로워집니다.")

# --- 🚀 핵심 분석 로직 (v9.0) ---
def analyze_stock(ticker, df, atr_k, market):
    try:
        # 1. 기술적 지표 계산
        df.ta.sma(length=200, append=True) # 장기 추세
        df.ta.sma(length=20, append=True)  # 단기 추세
        df.ta.rsi(length=14, append=True)
        df.ta.bbands(length=20, std=2, append=True)
        df.ta.atr(length=14, append=True)
        
        # 2. 피봇 포인트 (Pivot Points) 계산 - 정적 지지/저항
        # 전일 고/저/종가를 이용해 오늘의 지지/저항 계산 (Classic 방식)
        high = df['high'].iloc[-2]
        low = df['low'].iloc[-2]
        close_prev = df['close'].iloc[-2]
        
        pivot = (high + low + close_prev) / 3
        r1 = (2 * pivot) - low   # 1차 저항 (목표가 1)
        s1 = (2 * pivot) - high  # 1차 지지 (물타기 지점)
        
        # 데이터 정리
        df.dropna(inplace=True)
        if df.empty: return None

        latest = df.iloc[-1]
        curr_price = latest['close']
        
        # 컬럼 매핑
        sma200 = latest.get('SMA_200', 0)
        sma20 = latest.get('SMA_20', 0)
        rsi = latest.get('RSI_14', 50)
        bbl = latest.get('BBL_20_2.0', 0)
        atr = latest.get('ATRr_14', 0)
        
        # 3. 손절가 (ATR 기반)
        stop_price = curr_price - (atr * atr_k)
        
        # 4. 종합 스코어링 (0~100점)
        score = 0
        reasons = []
        
        # (1) 추세 점수 (40점)
        if curr_price > sma200: 
            score += 20
            reasons.append("장기상승")
        if curr_price > sma20: 
            score += 20
            reasons.append("단기상승")
            
        # (2) 위치/모멘텀 점수 (30점) - 눌림목인가?
        dist_to_bbl = (curr_price - bbl) / bbl
        if dist_to_bbl < 0.02: # 밴드 하단 근접 (2% 이내)
            score += 20
            reasons.append("밴드하단")
        elif dist_to_bbl < 0.05:
            score += 10
        
        if rsi < 35: 
            score += 10
            reasons.append("과매도")
        elif rsi < 45: 
            score += 5
            
        # (3) 거래량 점수 (30점)
        vol_avg = df['volume'].rolling(20).mean().iloc[-1]
        if latest['volume'] > vol_avg * 1.5:
            score += 30
            reasons.append("거래폭발")
        elif latest['volume'] > vol_avg:
            score += 10

        # 5. 신호 판정
        signal = "관망"
        if score >= 70: signal = "🔥 강력 매수"
        elif score >= 50: signal = "✅ 매수 고려"
        elif score <= 20: signal = "⚠️ 매도 주의"
        
        # 통화 및 포맷
        currency = "₩" if market == '한국 증시 (Korea)' else "$"
        fmt = ",.0f" if market == '한국 증시 (Korea)' else ",.2f"
        
        return {
            "티커": ticker,
            "종목명": "", # 나중에 채움
            "점수": score,
            "신호": signal,
            "현재가": f"{currency}{format(curr_price, fmt)}",
            "손절가": f"{currency}{format(stop_price, fmt)}",
            "1차저항(목표)": f"{currency}{format(r1, fmt)}", # 피봇 저항
            "핵심요인": ", ".join(reasons) if reasons else "특이사항 없음",
            "RSI": round(rsi, 1)
        }

    except Exception as e:
        return {"티커": ticker, "신호": "오류", "핵심요인": str(e)}

# --- 메인 실행 ---
if st.sidebar.button("🚀 프로 분석 시작!", type="primary"):
    tickers_raw = [t.strip().upper() for t in tickers_input.split(',') if t.strip()]
    tickers = []
    
    # 티커 보정
    for t in tickers_raw:
        if market_choice == '한국 증시 (Korea)' and not (t.endswith('.KS') or t.endswith('.KQ')):
             tickers.append(f"{t}.KS")
        else:
             tickers.append(t)
             
    if not tickers:
        st.warning("분석할 종목을 입력해주세요.")
    else:
        results = []
        bar = st.progress(0, "데이터 수집 중...")
        
        for i, ticker in enumerate(tickers):
            name = get_stock_name(ticker)
            bar.progress((i)/len(tickers), f"[{name}] 분석 중...")
            
            try:
                # 데이터 다운로드 (코스닥 재시도 로직 포함)
                df = yf.download(ticker, period="1y", progress=False, auto_adjust=True)
                if df.empty and market_choice == '한국 증시 (Korea)' and ticker.endswith(".KS"):
                    ticker = ticker.replace(".KS", ".KQ")
                    df = yf.download(ticker, period="1y", progress=False, auto_adjust=True)
                    name = get_stock_name(ticker) # 이름 갱신

                # 멀티인덱스/컬럼 소문자 처리
                if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0).str.lower()
                else: df.columns = df.columns.str.lower()

                if len(df) > 100:
                    res = analyze_stock(ticker, df, stop_loss_k, market_choice)
                    if res:
                        res["종목명"] = name
                        results.append(res)
            except: pass
            
        bar.empty()
        
        if results:
            df_res = pd.DataFrame(results)
            # 점수 높은 순 정렬
            df_res = df_res.sort_values(by="점수", ascending=False)
            
            st.success(f"분석 완료! ({len(results)}개)")
            
            # 스타일링 (가독성 향상)
            st.dataframe(
                df_res.style.background_gradient(subset=['점수'], cmap='RdYlGn', vmin=0, vmax=100)
                .format({'RSI': '{:.1f}'}),
                use_container_width=True,
                hide_index=True
            )
            
            # 상세 설명
            with st.expander("📊 결과 해석 가이드"):
                st.markdown("""
                * **점수:** 100점에 가까울수록 상승 추세와 모멘텀이 강합니다.
                * **손절가:** ATR 기반으로 계산된 '추세가 깨지는' 가격입니다.
                * **1차저항(목표):** 피봇(Pivot) 포인트로 계산된 단기 목표가입니다. 이 가격에 도달하면 분할 매도를 고려하세요.
                * **핵심요인:** 왜 이 점수가 나왔는지 알려줍니다 (예: 거래폭발, 밴드하단 등).
                """)
                
# --- 관심종목 관리 (기존 유지) ---
st.sidebar.divider()
with st.sidebar.expander("❤️ 관심종목 편집"):
    new_t = st.text_input("추가", placeholder="예: AAPL").upper()
    if st.button("➕ 추가"):
        if new_t and new_t not in st.session_state.watchlist:
            new_l = st.session_state.watchlist + [new_t]
            if save_watchlist(new_l): 
                st.session_state.watchlist = new_l
                st.rerun()
    for t in st.session_state.watchlist:
        c1, c2 = st.columns([0.8, 0.2])
        c1.text(f"- {t}")
        if c2.button("X", key=f"d_{t}"):
            new_l = [x for x in st.session_state.watchlist if x != t]
            if save_watchlist(new_l): 
                st.session_state.watchlist = new_l
                st.rerun()
