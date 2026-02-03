
import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta

# --- 페이지 설정 ---
st.set_page_config(page_title="Quant Screener", layout="wide")

# v3.2로 버전 업데이트
st.title("📈 AI 퀀트 종목 발굴기 (v3.2 - 안정성 강화)")
st.markdown(""" 
**알고리즘 로직:**
1. **추세 필터:** 200일 이동평균선 위에 있는 '상승 추세' 종목을 대상으로 분석
2. **거래량 필터:** 20일 평균 거래량 대비 현재 거래량의 급증 여부 확인
3. **타이밍 포착:** 볼린저 밴드 하단 터치 및 RSI 과매도 시그널 확인
4. **리스크 관리:** 설정된 손절 라인 자동 계산
---
**v3.2 변경점:** 일부 종목에서 발생하는 복잡한 데이터 구조(MultiIndex) 오류를 사전에 감지하고 처리하여, 앱의 안정성을 높였습니다.
""")

# --- 사이드바 설정 ---
st.sidebar.header("⚙️ 설정 (Settings)")
market_choice = st.sidebar.radio("시장 선택", ('미국 증시 (US)', '한국 증시 (Korea)'), horizontal=True)

# --- 종목 선택 UI ---
if market_choice == '한국 증시 (Korea)':
    presets = {
        "주요 기술주": "005930, 000660, 035420, 035720", "주요 자동차주": "005380, 000270",
        "주요 배터리주": "373220, 006400, 051910",
    }
    caption = "💡 종목 코드 입력 (예: 005930)"
    preset_key = st.sidebar.selectbox("종목 프리셋", presets.keys())
    tickers_input = st.sidebar.text_area("분석할 티커", presets[preset_key], height=100)
else: # 미국 증시
    presets = {
        "주요 기술주": "NVDA, AAPL, MSFT, GOOGL, AMD", "주요 성장주": "TSLA, PLTR, MSTR",
        "주요 ETF": "SPY, QQQ, TQQQ",
    }
    caption = "💡 티커 입력 (예: NVDA, TSLA)"
    preset_key = st.sidebar.selectbox("종목 프리셋", presets.keys())
    tickers_input = st.sidebar.text_area("분석할 티커", presets[preset_key], height=100)

st.sidebar.caption(caption)
stop_loss_pct = st.sidebar.slider("손절가 비율 (%)", 1.0, 10.0, 3.0, 0.5)

# --- 분석 함수 (안정성 강화) ---
@st.cache_data(ttl=300) # 5분 캐시
def analyze_stock(ticker):
    try:
        df = yf.download(ticker, period="1y", progress=False, auto_adjust=True)
        
        # ❗️ 핵심 수정: MultiIndex 구조 확인 및 처리
        if isinstance(df.columns, pd.MultiIndex):
            return {"티커": ticker, "신호": "오류", "오류 원인": "데이터 구조 복잡 (MultiIndex)"}

        if df.empty:
            return {"티커": ticker, "신호": "오류", "오류 원인": "데이터 없음 (티커 확인)"}
        if len(df) < 200:
            return {"티커": ticker, "신호": "오류", "오류 원인": f"데이터 부족 ({len(df)}일)"}

        df.ta.sma(length=200, append=True)
        df.ta.rsi(length=14, append=True)
        df.ta.bbands(length=20, std=2, append=True)
        df['Volume_MA20'] = df['Volume'].rolling(window=20).mean()

        required_cols = ['SMA_200', 'RSI_14', 'BBL_20_2.0', 'BBU_20_2.0', 'Volume_MA20']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            return {"티커": ticker, "신호": "오류", "오류 원인": f"지표 계산 실패: {missing_cols}"}

        df.dropna(inplace=True)
        if df.empty:
            return {"티커": ticker, "신호": "오류", "오류 원인": "데이터 정제 후 비어있음"}

        latest = df.iloc[-1]
        close, ma200, rsi, vol, vol_avg, bb_lower, bb_upper = latest[[
'Close', 'SMA_200', 'RSI_14', 'Volume', 'Volume_MA20', 'BBL_20_2.0', 'BBU_20_2.0'
]]

        trend = "상승" if close > ma200 else "하락"
        volume_signal = "급증" if vol_avg > 0 and vol > vol_avg * 1.5 else "보통"

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
        return {"티커": ticker, "신호": "오류", "오류 원인": f"알 수 없는 오류: {str(e)}"}

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
            data = analyze_stock(ticker)
            if data.get('신호') == '오류':
                error_results.append(data)
            else:
                ok_results.append(data)
            progress_bar.progress((i + 1) / len(tickers), text=f"{ticker} 분석 중...")

        # 성공 결과 표시
        if ok_results:
            st.subheader("📊 분석 결과")
            res_df = pd.DataFrame(ok_results)
            # ... (나머지 성공/실패 결과 표시 로직은 변경 없음)
            res_df['score'] = res_df['신호'].map({"🔥 강력 매수":0, "✅ 매수 고려":1, "관망":2, "🔻 이익 실현":3})
            res_df = res_df.sort_values(by="score").drop(columns=['score'])
            st.dataframe(res_df.style.format(
                {"현재가": "₩{:,.0f}" if market_choice == '한국 증시 (Korea)' else "${:,.2f}",
                 "손절가": "₩{:,.0f}" if market_choice == '한국 증시 (Korea)' else "${:,.2f}",
                 "RSI": "{:.1f}"}
            ), use_container_width=True, hide_index=True)

        # 실패 결과 표시
        if error_results:
            st.subheader("⚠️ 분석 실패 목록")
            error_df = pd.DataFrame(error_results)[['티커', '오류 원인']]
            st.dataframe(error_df, use_container_width=True, hide_index=True)
            
        if not ok_results and not error_results:
            st.warning("분석 결과가 없습니다. 티커를 확인하거나 다른 종목을 시도해보세요.")
