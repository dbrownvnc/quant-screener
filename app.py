
import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import requests
import json
import re
import time
import finance_datareader as fdr

# --- 페이지 설정 ---
st.set_page_config(page_title="Quant Screener v9.5", layout="wide")

st.title("📈 AI 퀀트 종목 발굴기 (v9.5 - 대량 분석 최적화)")

with st.expander("✨ 앱 소개 및 v9.5 변경점"):
    st.markdown('''
    **AI 퀀트 종목 발굴기는 기술적 분석 지표를 종합하여 매수 타이밍에 근접한 종목을 찾아냅니다.**

    **v9.5 핵심 기능:**
    1.  **대량 분석 모드 (속도 30배 향상):**
        *   분석할 종목 입력창을 비워두고 `분석 시작` 버튼을 누르면, **시장별 주요 종목 전체(S&P500, NASDAQ, KOSPI, KOSDAQ)를 자동으로 분석**합니다.
        *   30~50개 종목을 하나의 그룹으로 묶어 동시에 데이터를 요청하는 **배치(Batch) 처리 방식**을 도입하여, 수백 개의 종목을 수 분 내로 빠르게 스크리닝합니다.
    2.  **스마트한 리소스 관리:**
        *   `매수` 신호가 포착된 유망 종목에 대해서만 상세 정보(종목명 등)를 추가 조회하여 불필요한 API 요청을 최소화합니다.
        *   각 데이터 요청 그룹 사이에 적절한 휴식(1초)을 두어 API 차단을 예방합니다.
    3.  **직관적인 위험 신호:** 1차 지지선(S1)이 붕괴된 종목은 2차 지지선(S2)과 함께 `(S1 붕괴⚠️)` 경고를 명확히 표시합니다.
    ''')

# --- 핵심 분석/유틸리티 함수 ---

@st.cache_data(ttl=86400)
def get_stock_name(ticker):
    hotfix_map = {
        "005930.KS": "삼성전자", "000660.KS": "SK하이닉스",
        "373220.KS": "LG에너지솔루션", "373220.KQ": "LG에너지솔루션"
    }
    if ticker.upper() in hotfix_map:
        return hotfix_map[ticker.upper()]
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
    try:
        stock = yf.Ticker(ticker)
        name = stock.info.get('longName') or stock.info.get('shortName')
        if name: return name
    except Exception: pass
    return ticker

def get_pivot_points(df):
    if len(df) < 2: return 0, 0, 0
    last = df.iloc[-2]
    high, low, close = last['high'], last['low'], last['close']
    pivot = (high + low + close) / 3
    s1 = (2 * pivot) - high
    r1 = (2 * pivot) - low
    s2 = pivot - (high - low)
    return s1, r1, s2

@st.cache_data(ttl=600)
def get_market_tickers(market):
    if market == '미국 증시 (US)':
        sp500 = fdr.StockListing('S&P500')['Symbol'].tolist()
        nasdaq = fdr.StockListing('NASDAQ')['Symbol'].tolist()
        return list(set(sp500 + nasdaq))
    else:
        kospi = fdr.StockListing('KOSPI')['Code'].tolist()
        kosdaq = fdr.StockListing('KOSDAQ')['Code'].tolist()
        return [f"{t}.KS" for t in kospi] + [f"{t}.KQ" for t in kosdaq]

# --- JSONBIN.IO (관심종목 저장) 설정 ---
api_key_names = ["JSONBIN_API_KEY", "jsonbin_api_key"]
bin_id_names = ["JSONBIN_BIN_ID", "jsonbin_bin_id"]
JSONBIN_API_KEY = next((st.secrets.get(key) for key in api_key_names), None)
JSONBIN_BIN_ID = next((st.secrets.get(key) for key in bin_id_names), None)

if not JSONBIN_API_KEY or not JSONBIN_BIN_ID:
    st.error("⚠️ [설정 오류] Secrets 설정을 확인해주세요 (JSONBIN_API_KEY, JSONBIN_BIN_ID).")
    st.stop()

JSONBIN_URL = f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}"
HEADERS = {'Content-Type': 'application/json', 'X-Master-Key': JSONBIN_API_KEY}

@st.cache_data(ttl=300)
def load_watchlist_from_jsonbin():
    try:
        response = requests.get(f"{JSONBIN_URL}/latest", headers=HEADERS, timeout=5)
        response.raise_for_status()
        return response.json().get('record', {}).get('watchlist', [])
    except Exception: return []

def save_watchlist_to_jsonbin(watchlist_data):
    try:
        requests.put(JSONBIN_URL, headers=HEADERS, json={'watchlist': watchlist_data}, timeout=5).raise_for_status()
        st.cache_data.clear()
        return True
    except Exception: return False

# --- 세션 초기화 ---
if 'watchlist_loaded' not in st.session_state:
    st.session_state.watchlist = load_watchlist_from_jsonbin()
    st.session_state.watchlist_loaded = True

# --- 사이드바 UI ---
market_choice = st.sidebar.radio("시장 선택", ('미국 증시 (US)', '한국 증시 (Korea)'), horizontal=True)
watchlist_str = ", ".join(st.session_state.watchlist)

# 프리셋
if market_choice == '한국 증시 (Korea)':
    presets = {
        "❤️ 내 관심종목": watchlist_str,
        "💾 반도체 주요": "005930,000660,042700,000020,095340.KQ",
        "🔋 2차전지 주요": "373220,006400,051910,247540.KQ,086520.KQ",
        "기타 주요주": "005380,035420,035720,267250,207940"
    }
    caption = "💡 전체 분석은 비우고 시작. 개별은 코드 입력. (예: 005930)"
else:
    presets = {
        "❤️ 내 관심종목": watchlist_str,
        "👑 M7": "NVDA,AAPL,MSFT,GOOGL,AMZN,META,TSLA",
        "🤖 AI & 반도체": "NVDA,AMD,AVGO,TSM,MU,SMCI,PLTR",
        "기타 주요주": "LLY,NVO,MSTR,COIN,LMT,BA"
    }
    caption = "💡 전체 분석은 비우고 시작. 개별은 티커 입력. (예: NVDA, TSLA)"

preset_key = st.sidebar.selectbox("종목 프리셋", presets.keys())
tickers_input = st.sidebar.text_area("분석할 티커", presets[preset_key], height=100)
st.sidebar.caption(caption)
run_analysis_button = st.sidebar.button("🚀 AI 퀀트 분석 시작!", type="primary")

st.sidebar.divider()
st.sidebar.subheader("🛡️ 리스크 관리 (손절)")
stop_loss_mode = st.sidebar.radio("계산 방식", ("ATR 기반 (권장)", "피봇 지지선 (S1) 기준", "고정 비율 (%)"), horizontal=True)
atr_multiplier = st.sidebar.slider("ATR 배수 (k)", 1.0, 5.0, 2.0, 0.1) if stop_loss_mode == "ATR 기반 (권장)" else 0
stop_loss_pct = st.sidebar.slider("손절 비율 (%)", 1.0, 10.0, 3.0, 0.5) if stop_loss_mode == "고정 비율 (%)" else 0

# --- 분석 로직 ---
def analyze_dataframe(ticker, df, stop_loss_mode, market, **kwargs):
    try:
        # 지표 계산
        df.ta.sma(length=200, append=True)
        df.ta.rsi(length=14, append=True)
        df.ta.bbands(length=20, std=2, append=True)
        df.ta.atr(length=14, append=True)
        df.dropna(inplace=True)
        if df.empty: return None

        latest = df.iloc[-1]
        close = latest['close']
        currency = "₩" if market == '한국 증시 (Korea)' else "$"
        
        # 지지/저항
        s1, r1, s2 = get_pivot_points(df)
        support_display = f"{currency}{s1:,.0f}" if s1 > 0 else "N/A"
        if s1 > 0 and close < s1:
            support_display = f"{currency}{s2:,.0f} (S1 붕괴⚠️)"

        # 신호 로직
        score, reasons = 0, []
        if close <= latest[df.columns[df.columns.str.contains('BBL', case=False)][0]] * 1.01:
            score += 1; reasons.append("볼린저 하단")
        if s1 > 0 and (s1 * 0.99 <= close <= s1 * 1.03):
            score += 1; reasons.append("피봇 지지")
        if close <= df['low'].tail(20).min() * 1.03:
            score += 1; reasons.append("전저점 근접")
        if latest['RSI_14'] < 35: score += 1
        
        trend = "상승" if close > latest[df.columns[df.columns.str.contains('SMA_200', case=False)][0]] else "하락"
        signal = "관망"
        if trend == "상승":
            if score >= 2: signal = f"🔥 강력 매수 ({', '.join(reasons)})"
            elif score == 1 and latest['RSI_14'] < 45: signal = f"✅ 매수 고려 ({reasons[0]})"

        # 거래량
        vol_signal = "보통"
        if 'volume' in df.columns and len(df) > 20:
            vol_avg_20 = df['volume'].rolling(20).mean().iloc[-1]
            if latest['volume'] > vol_avg_20 * 1.5:
                vol_signal = "⬆️ 양봉 급증" if close > latest['open'] else "⬇️ 음봉 급증"
        
        # 손절가
        atr_col = df.columns[df.columns.str.contains('ATRr', case=False)][0]
        loss_info = "N/A"
        if stop_loss_mode == "ATR 기반 (권장)":
            loss_price = close - (latest[atr_col] * kwargs.get('atr_multiplier', 2.0))
            loss_info = f"{currency}{loss_price:,.0f} (-{((close - loss_price) / close) * 100:.1f}%)"
        elif stop_loss_mode == "피봇 지지선 (S1) 기준":
            if s1 > 0: loss_info = f"{currency}{s1:,.0f} (피봇 S1)"
        else:
            loss_price = close * (1 - kwargs.get('stop_loss_pct', 3.0) / 100)
            loss_info = f"{currency}{loss_price:,.0f} (-{kwargs.get('stop_loss_pct', 3.0)}%)"

        return {
            "티커": ticker, "신호": signal, "현재가": close, "손절가": loss_info,
            "지지(S1)": support_display, "저항(R1)": r1, "RSI": latest['RSI_14'],
            "추세": trend, "거래량": vol_signal
        }
    except Exception: return None

# --- 실행 로직 (v9.5 Batch Processing) ---
if run_analysis_button:
    # 1. 분석 대상 티커 확보
    if not tickers_input.strip():
        st.info(f"📋 {market_choice} 주요 종목 전체를 분석합니다. (S&P500, NASDAQ, KOSPI, KOSDAQ)")
        tickers = get_market_tickers(market_choice)
    else:
        tickers_raw = [t.strip().upper() for t in tickers_input.split(',') if t.strip()]
        tickers = []
        for t in tickers_raw:
            if market_choice == '한국 증시 (Korea)' and not (t.endswith('.KS') or t.endswith('.KQ')):
                tickers.append(f"{t}.KS")
            else:
                tickers.append(t)

    if not tickers:
        st.warning("분석할 종목이 없습니다.")
    else:
        st.write(f"🔍 총 {len(tickers)}개 종목 분석을 시작합니다. (배치 모드)")
        
        ok_results, error_results = [], []
        
        # 2. 배치 설정
        BATCH_SIZE = 50
        total_batches = (len(tickers) + BATCH_SIZE - 1) // BATCH_SIZE
        progress_bar = st.progress(0)
        status_text = st.empty()

        for i in range(0, len(tickers), BATCH_SIZE):
            batch_tickers = tickers[i : i + BATCH_SIZE]
            current_batch_num = (i // BATCH_SIZE) + 1
            status_text.text(f"⏳ 그룹 {current_batch_num}/{total_batches} 데이터 수집 중... ({len(batch_tickers)}개 종목)")
            
            try:
                # 3. yfinance 대량 다운로드
                data = yf.download(batch_tickers, period="1y", group_by='ticker', threads=True, progress=False, auto_adjust=True)
                
                # 4. 데이터 쪼개서 개별 분석
                for ticker in batch_tickers:
                    try:
                        df = data[ticker].copy() if len(batch_tickers) > 1 else data.copy()
                        
                        if df.empty or df['Close'].isna().all() or len(df) < 100: continue
                        
                        df.columns = df.columns.str.lower()
                        
                        res = analyze_dataframe(ticker, df, stop_loss_mode, market_choice, atr_multiplier=atr_multiplier, stop_loss_pct=stop_loss_pct)
                        
                        if res:
                            if "매수" in res["신호"]:
                                res["종목명"] = get_stock_name(ticker)
                            else:
                                res["종목명"] = ticker
                            ok_results.append(res)
                            
                    except Exception: continue

            except Exception as e:
                error_results.extend(batch_tickers)
            
            # 5. 차단 방지 휴식 및 진행률 업데이트
            progress_bar.progress(min((i + BATCH_SIZE) / len(tickers), 1.0))
            time.sleep(1)

        progress_bar.empty()
        status_text.empty()

        # --- 결과 출력 ---
        if ok_results:
            st.success(f"✅ 분석 완료! 총 {len(tickers)}개 중 {len(ok_results)}개 결과 도출")
            
            view_option = st.radio("보기 옵션", ["전체 보기", "🔥 강력 매수만 보기", "✅ 매수 고려 이상 보기"], horizontal=True, key="view_filter")
            
            res_df = pd.DataFrame(ok_results)
            
            if view_option == "🔥 강력 매수만 보기":
                res_df = res_df[res_df['신호'].str.contains("강력 매수")]
            elif view_option == "✅ 매수 고려 이상 보기":
                res_df = res_df[res_df['신호'].str.contains("매수")]

            if res_df.empty:
                st.info("조건에 맞는 종목이 없습니다.")
            else:
                signal_order = {'🔥': 0, '✅': 1, '관': 2}
                res_df['sort_key'] = res_df['신호'].apply(lambda x: signal_order.get(x[0], 99))
                res_df = res_df.sort_values(by='sort_key').drop(columns=['sort_key'])
                
                currency_format = "₩{:,.0f}" if market_choice == '한국 증시 (Korea)' else "${:,.2f}"
                cols = ["티커", "종목명", "신호", "현재가", "손절가", "지지(S1)", "저항(R1)", "RSI", "거래량", "추세"]
                final_df = res_df[[c for c in cols if c in res_df.columns]]
                
                styler = final_df.style.format({
                    "현재가": currency_format, 
                    "저항(R1)": currency_format,
                    "RSI": "{:.1f}"
                })
                styler.set_properties(**{'font-size': '13px', 'text-align': 'center'})
                st.dataframe(styler, use_container_width=True, hide_index=True)
        else:
            st.warning("분석 결과가 없거나, 모든 종목의 데이터 수집에 실패했습니다.")
        
        if error_results:
            st.error(f"⚠️ 데이터 수집에 실패한 종목이 {len(error_results)}개 있습니다: {', '.join(error_results[:10])}...")


# --- 관심종목 관리 UI ---
st.sidebar.divider()
st.sidebar.subheader("❤️ 관심종목 관리")
with st.sidebar.expander("목록 편집"):
    new_t = st.text_input("추가", placeholder="예: 005930").upper()
    if st.button("➕ 저장"):
        if new_t and new_t not in st.session_state.watchlist:
            new_l = st.session_state.watchlist + [new_t]
            if save_watchlist_to_jsonbin(new_l):
                st.session_state.watchlist = new_l; st.rerun()
    
    for t in st.session_state.watchlist:
        c1, c2 = st.columns([0.8, 0.2])
        c1.text(f"- {t}")
        if c2.button("X", key=f"d_{t}"):
            new_l = [x for x in st.session_state.watchlist if x != t]
            if save_watchlist_to_jsonbin(new_l):
                st.session_state.watchlist = new_l; st.rerun()
