import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import datetime

# --- 페이지 설정 ---
st.set_page_config(page_title="Quant Chart Screener", layout="wide")

st.title("📈 AI 퀀트 종목 발굴기 (Pro Ver.)")
st.markdown("""
**알고리즘 로직:**
1. **추세 필터:** 200일 이동평균선 위에 있는 종목만 '상승 추세'로 인정
2. **거래량 필터:** 평균 거래량 대비 현재 거래량 급증 여부 확인
3. **진입 타이밍:** 볼린저 밴드 하단 터치 + RSI 과매도 (30 이하)
4. **리스크 관리:** 진입가 대비 -3% 자동 손절가 산출
""")

# --- 사이드바: 설정 ---
st.sidebar.header("설정 (Settings)")

# --- 종목 선택 ---
presets = {
    "주요 기술주": "005930, 000660, 035420, 035720",
    "주요 자동차주": "005380, 000270",
    "주요 배터리주": "373220, 006400, 051910"
}
preset_choice = st.sidebar.selectbox(
    "종목 프리셋 선택",
    options=list(presets.keys())
)

tickers_input = st.sidebar.text_area(
    "분석할 티커 (직접 수정 가능)",
    presets[preset_choice]
)

st.sidebar.caption("💡 종목 코드만 입력하세요 (자동으로 .KS 추가)")
stop_loss_pct = st.sidebar.slider("손절가 비율 설정 (%)", 1, 10, 3)


# --- 분석 함수 ---
def analyze_stock(ticker):
    try:
        # 데이터 다운로드 (최근 1년치 - 200일선 계산 위해 충분히)
        df = yf.download(ticker, period="1y", progress=False)

        if df.empty:
            st.error(f"'{ticker}'에 대한 데이터를 찾을 수 없습니다. 티커를 확인해주세요.")
            return None
        if len(df) < 200:
            st.warning(f"'{ticker}'에 대한 데이터가 부족하여 분석할 수 없습니다. (200일 미만)")
            return None # 데이터 부족

        # 1. 기술적 지표 계산
        # 이동평균선
        df['MA20'] = df['Close'].rolling(window=20).mean()
        df['MA200'] = df['Close'].rolling(window=200).mean()

        # 볼린저 밴드
        bb = ta.bbands(df['Close'], length=20, std=2)
        df = pd.concat([df, bb], axis=1) # 데이터프레임 병합

        # RSI
        df['RSI'] = ta.rsi(df['Close'], length=14)

        # 거래량 이동평균 (20일)
        df['Vol_MA20'] = df['Volume'].rolling(window=20).mean()

        # --- 최신 데이터 추출 ---
        latest = df.iloc[-1]
        close = latest['Close']
        ma200 = latest['MA200']
        rsi = latest['RSI']
        vol = latest['Volume']
        vol_avg = latest['Vol_MA20']
        bb_lower = latest['BBL_20_2.0']
        bb_upper = latest['BBU_20_2.0']

        # 2. 필터링 로직 (Upgrade)

        # A. 추세 판단 (Trend Filter)
        trend = "상승세 (Bull)" if close > ma200 else "하락세 (Bear)"
        trend_score = 1 if close > ma200 else 0

        # B. 거래량 판단 (Volume Filter)
        vol_ratio = (vol / vol_avg) * 100 # 평소 대비 거래량 %
        vol_status = "거래량 폭발" if vol_ratio > 150 else "보통"

        # C. 매매 신호 (Signal)
        signal = "관망"
        color = "gray"

        # 매수 조건: 상승 추세이고 + 밴드 하단 근처 + RSI 낮음
        if close > ma200: # 장기 상승 추세일 때만 매수 고려 (안전)
            if close <= bb_lower * 1.02 and rsi < 45:
                signal = "🔥 강력 매수 (눌림목)"
                color = "red"
            elif close <= bb_lower * 1.05 and vol_ratio > 120:
                signal = "✅ 매수 고려 (수급 동반)"
                color = "orange"

        # 매도 조건: 밴드 상단 근처 + RSI 과열
        if close >= bb_upper * 0.98 and rsi > 70:
            signal = "🔻 이익 실현 (과열)"
            color = "blue"

        # D. 손절가 계산 (Stop Loss)
        stop_price = close * (1 - (stop_loss_pct / 100))

        return {
            "티커": ticker,
            "현재가": round(close, 2),
            "신호": signal,
            "추세": trend,
            "거래량": vol_status,
            "RSI": round(rsi, 1),
            "손절가": round(stop_price, 2),
            "차트": df,
            "컬러": color
        }
    except Exception as e:
        st.error(f"'{ticker}' 분석 중 오류 발생: {e}")
        return None

# --- 메인 화면 ---
if st.sidebar.button("종목 분석 시작"):
    tickers = [t.strip() for t in tickers_input.split(',')]
    
    # 한국 주식 티커 자동 변환 (숫자로만 된 경우 .KS 추가)
    processed_tickers = []
    for t in tickers:
        if t.isdigit() and len(t) == 6:
             processed_tickers.append(f"{t}.KS")
        else:
             processed_tickers.append(t)

    results = []
    with st.spinner("AI가 종목을 분석중입니다... 잠시만 기다려주세요."):
        for ticker in processed_tickers:
            analysis = analyze_stock(ticker)
            if analysis:
                results.append(analysis)

    if not results:
        st.warning("유효한 분석 결과가 없습니다. 티커를 확인하거나 다른 종목을 시도해보세요.")
    else:
        # --- 결과 정렬 ---
        # 신호 강도에 따라 정렬 (강력매수 > 매수고려 > 관망 > 이익실현 순)
        signal_order = {"🔥 강력 매수 (눌림목)": 0, "✅ 매수 고려 (수급 동반)": 1, "관망": 2, "🔻 이익 실현 (과열)": 3}
        results.sort(key=lambda x: signal_order.get(x['신호'], 99))

        st.subheader("종목 분석 결과")
        
        # 결과 표시 컬럼 수 동적 조절
        num_results = len(results)
        num_columns = min(num_results, 3) # 최대 3개 컬럼
        if num_columns == 0:
            st.info("분석할 종목이 없습니다.")
            st.stop()
            
        cols = st.columns(num_columns) 

        for i, res in enumerate(results):
            col = cols[i % num_columns]
            with col:
                st.markdown(f"""
                <div style="border: 2px solid {res['컬러']}; border-radius: 10px; padding: 15px; margin-bottom: 20px;">
                    <h3 style="color: {res['컬러']};">{res['티커']}: <span style="font-weight: normal;">{res['신호']}</span></h3>
                    <ul>
                        <li><b>현재가:</b> {res['현재가']:,}</li>
                        <li><b>추세:</b> {res['추세']}</li>
                        <li><b>거래량:</b> {res['거래량']}</li>
                        <li><b>RSI:</b> {res['RSI']}</li>
                        <li><b>손절가:</b> <span style="color: #FF4B4B;">{res['손절가']:,}</span></li>
                    </ul>
                </div>
                """, unsafe_allow_html=True)

                # --- 미니 차트 ---
                st.line_chart(res['차트']['Close'][-60:], height=150) # 최근 60일 종가
