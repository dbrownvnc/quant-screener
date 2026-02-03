
import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta

# --- 페이지 설정 ---
st.set_page_config(page_title="Quant Screener", layout="wide")

# v5.0: 관심종목 관리 기능 추가
st.title("📈 AI 퀀트 종목 발굴기 (v5.0)")
st.markdown("""
**알고리즘 로직:**
1.  **추세 필터:** 200일 이동평균선 위에 있는 '상승 추세' 종목을 대상으로 분석
2.  **거래량 필터:** 20일 평균 거래량 대비 현재 거래량의 급증 여부 확인
3.  **타이밍 포착:** 볼린저 밴드 하단 터치 및 RSI 과매도 시그널 확인
4.  **리스크 관리:** 설정된 손절 라인 자동 계산
---
**v5.0 변경점:**
1.  **관심종목 관리 기능:** 사이드바에서 직접 관심종목을 추가/삭제하고, '관심종목' 프리셋을 선택하여 바로 분석할 수 있습니다.
2.  **v4.2 안정화 로직 유지:** `pandas-ta` 라이브러리의 컬럼 이름 변경에 대응하는 동적 컬럼 탐색 기능은 그대로 유지됩니다.
""")

# --- 세션 상태 초기화 ---
if 'watchlist' not in st.session_state:
    st.session_state.watchlist = []

# --- 사이드바 설정 ---
st.sidebar.header("⚙️ 설정 (Settings)")
market_choice = st.sidebar.radio("시장 선택", ('미국 증시 (US)', '한국 증시 (Korea)'), horizontal=True)

# --- 관심종목 관리 UI ---
st.sidebar.subheader("❤️ 관심종목 관리")
new_ticker = st.sidebar.text_input("티커 추가", placeholder="예: NVDA, 005930").upper()

if st.sidebar.button("➕ 추가"):
    if new_ticker and new_ticker not in st.session_state.watchlist:
        st.session_state.watchlist.append(new_ticker)
        st.sidebar.success(f"'{new_ticker}'를 관심종목에 추가했습니다.")
    elif new_ticker in st.session_state.watchlist:
        st.sidebar.warning(f"'{new_ticker}'는 이미 목록에 있습니다.")
    else:
        st.sidebar.warning("추가할 티커를 입력해주세요.")

# 관심종목 목록 표시 및 삭제 기능
if st.session_state.watchlist:
    st.sidebar.markdown("내 관심종목:")
    # Use a loop that allows safe removal
    for ticker_to_remove in st.session_state.watchlist[:]:
        col1, col2 = st.sidebar.columns([0.8, 0.2])
        with col1:
            st.markdown(f"- {ticker_to_remove}")
        with col2:
            # Use a unique key for each button
            if st.button(f"🗑️", key=f"del_{ticker_to_remove}", help=f"{ticker_to_remove} 삭제"):
                st.session_state.watchlist.remove(ticker_to_remove)
                st.rerun() # Re-run the script to update the UI immediately
else:
    st.sidebar.caption("추가된 관심종목이 없습니다.")

st.sidebar.divider()

# --- 종목 선택 UI ---
watchlist_str = ", ".join(st.session_state.watchlist)

if market_choice == '한국 증시 (Korea)':
    presets = {
        "관심종목 (My Watchlist)": watchlist_str,
        "주요 기술주": "005930, 000660, 035420, 035720",
        "주요 자동차주": "005380, 000270",
        "주요 배터리주": "373220, 006400, 051910",
    }
    caption = "💡 종목 코드 입력 (예: 005930)"
else: # 미국 증시
    presets = {
        "관심종목 (My Watchlist)": watchlist_str,
        "주요 기술주": "NVDA, AAPL, MSFT, GOOGL, AMD",
        "주요 성장주": "TSLA, PLTR, MSTR",
        "주요 ETF": "SPY, QQQ, TQQQ",
    }
    caption = "💡 티커 입력 (예: NVDA, TSLA)"

# Make sure the default selection exists even if watchlist is empty
preset_options = list(presets.keys())
preset_key = st.sidebar.selectbox("종목 프리셋", preset_options)
# The text_area's default value is now correctly keyed to the presets dictionary
tickers_input = st.sidebar.text_area("분석할 티커", presets[preset_key], height=100)


st.sidebar.caption(caption)
stop_loss_pct = st.sidebar.slider("손절가 비율 (%)", 1.0, 10.0, 3.0, 0.5)

# --- 분석 함수 (v4.2 로직 유지) ---
def analyze_dataframe(ticker, df, stop_loss_pct):
    # (The rest of the analysis function remains unchanged)
    try:
        df.ta.sma(length=200, append=True)
        df.ta.rsi(length=14, append=True)
        df.ta.bbands(length=20, std=2, append=True) # 컬럼 이름 이슈가 있던 함수

        df.dropna(inplace=True)
        if df.empty:
            return {"티커": ticker, "신호": "오류", "오류 원인": "데이터 정제 후 비어있음"}

        # ❗️ 핵심 수정 (v4.2): 볼린저 밴드 하단 컬럼을 동적으로 찾기
        bbl_col_name = next((col for col in df.columns if col.startswith('BBL')), None)
        bbu_col_name = next((col for col in df.columns if col.startswith('BBU')), None)

        if not bbl_col_name or not bbu_col_name:
            return {"티커": ticker, "신호": "오류", "오류 원인": "볼린저 밴드 컬럼 동적 탐색 실패"}
        
        # ❗️ SMA 컬럼도 만일을 위해 동적으로 찾기
        sma200_col_name = next((col for col in df.columns if col.startswith('SMA_200')), None)
        if not sma200_col_name:
             return {"티커": ticker, "신호": "오류", "오류 원인": "SMA_200 컬럼 동적 탐색 실패"}

        if 'volume' in df.columns:
            df['volume_ma20'] = df['volume'].rolling(window=20).mean()

        latest = df.iloc[-1]
        
        # 동적으로 찾은 컬럼 이름 사용
        close = latest['close']
        ma200 = latest[sma200_col_name]
        rsi = latest['RSI_14']
        bb_lower = latest[bbl_col_name]
        bb_upper = latest[bbu_col_name]
        
        volume_signal = "N/A"
        if 'volume_ma20' in latest and latest['volume_ma20'] > 0:
            vol = latest['volume']
            vol_avg = latest['volume_ma20']
            volume_signal = "급증" if vol > vol_avg * 1.5 else "보통"
        
        trend = "상승" if close > ma200 else "하락"
        signal = "관망"
        if close > ma200:
            if close <= bb_lower and rsi < 35:
                signal = "🔥 강력 매수"
            elif close <= bb_lower * 1.03 and rsi < 45:
                signal = "✅ 매수 고려"
        if close >= bb_upper and rsi > 65:
            signal = "🔻 이익 실현"

        stop_price = close * (1 - (stop_loss_pct / 100))

        return {
            "티커": ticker, "신호": signal, "현재가": close,
            "추세": trend, "RSI": rsi, "거래량": volume_signal, "손절가": stop_price,
        }
    except Exception as e:
        return {"티커": ticker, "신호": "오류", "오류 원인": f"분석 로직 오류: {str(e)}"}

# --- 실행 버튼 및 결과 표시 ---
if st.sidebar.button("🚀 AI 퀀트 분석 시작!"):
    tickers_raw = [t.strip().upper() for t in tickers_input.split(',') if t.strip()]
    tickers = [f"{t}.KS" for t in tickers_raw] if market_choice == '한국 증시 (Korea)' else tickers_raw

    if not tickers:
        st.warning("분석할 종목이 없습니다. 티커를 입력해주세요.")
    else:
        ok_results, error_results = [], []
        progress_bar = st.progress(0, text="분석 시작...")

        for i, ticker in enumerate(tickers):
            progress_bar.progress((i + 1) / len(tickers), text=f"[{ticker}] 데이터 다운로드 중...")
            
            try:
                df = yf.download(ticker, period="1y", progress=False, auto_adjust=True)

                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                    df.columns = [str(col).lower() for col in df.columns]

                if df.empty:
                    raise ValueError("데이터 없음 (티커를 확인해주세요)")

                required_cols_data = ['open', 'high', 'low', 'close']
                for col in required_cols_data + ['volume']:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors='coerce')

                missing_cols = [col for col in required_cols_data if col not in df.columns]
                if missing_cols:
                    raise ValueError(f"필수 OHLC 데이터 부족: {missing_cols}")

                if df['close'].count() < 200:
                    st.warning(f"[{ticker}] 분석 건너뛰기: 데이터 부족 (200일 미만)")
                    continue

                progress_bar.progress((i + 1) / len(tickers), text=f"[{ticker}] 기술 지표 분석 중...")
                analysis_result = analyze_dataframe(ticker, df.copy(), stop_loss_pct)
                
                if analysis_result.get('신호') == '오류':
                    error_results.append(analysis_result)
                else:
                    ok_results.append(analysis_result)

            except Exception as e:
                 error_results.append({"티커": ticker, "신호": "오류", "오류 원인": str(e)})

        progress_bar.empty()

        if ok_results:
            st.subheader("📊 분석 결과")
            res_df = pd.DataFrame(ok_results)
            res_df['score'] = res_df['신호'].map({"🔥 강력 매수":0, "✅ 매수 고려":1, "관망":2, "🔻 이익 실현":3, "오류": 4})
            res_df = res_df.sort_values(by="score").drop(columns=['score'])
            st.dataframe(res_df.style.format(
                {"현재가": "₩{:,.0f}" if market_choice == '한국 증시 (Korea)' else "${:,.2f}",
                 "손절가": "₩{:,.0f}" if market_choice == '한국 증시 (Korea)' else "${:,.2f}",
                 "RSI": "{:.1f}"}
            ), use_container_width=True, hide_index=True)

        if error_results:
            st.subheader("⚠️ 분석 실패 목록")
            error_df = pd.DataFrame(error_results)[['티커', '오류 원인']]
            st.dataframe(error_df, use_container_width=True, hide_index=True)

        if not ok_results and not error_results:
            st.warning("분석 결과가 없습니다. 티커를 확인하거나 다른 종목을 시도해보세요.")
