
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

# --- 데이터 기간 설정 ---
start_date = st.sidebar.date_input("분석 시작일", datetime.date(2023, 1, 1))
end_date = st.sidebar.date_input("분석 종료일", datetime.date.today())

# --- 분석 실행 버튼 ---
if st.sidebar.button("🚀 AI 퀀트 분석 시작!"):
    
    # --- 입력 처리 ---
    tickers = [f"{ticker.strip()}.KS" for ticker in tickers_input.split(',') if ticker.strip()]

    if not tickers:
        st.warning("분석할 종목이 없습니다. 티커를 입력해주세요.")
        st.stop()
        
    # --- 데이터 분석 ---
    @st.cache_data
    def analyze_ticker(ticker):
        try:
            # 1. 데이터 다운로드
            stock = yf.Ticker(ticker)
            df = stock.history(start=start_date, end=end_date)
            if df.empty:
                return None

            # 2. 기술적 지표 계산
            df['SMA_200'] = ta.sma(df['Close'], length=200)
            df['Volume_MA_20'] = ta.sma(df['Volume'], length=20)
            
            # 볼린저 밴드
            bollinger = ta.bbands(df['Close'], length=20, std=2)
            df = pd.concat([df, bollinger], axis=1)

            df['RSI'] = ta.rsi(df['Close'], length=14)

            # 3. 신호 생성
            latest = df.iloc[-1]
            
            # 추세 신호
            trend_signal = "상승 추세" if latest['Close'] > latest['SMA_200'] else "하락 추세"
            
            # 거래량 신호
            volume_signal = "거래량 급증" if latest['Volume'] > latest['Volume_MA_20'] * 1.5 else "거래량 보통"
            
            # 진입/이탈 신호
            buy_signal = "매수 고려" if latest['Close'] <= latest['BBL_20_2.0'] and latest['RSI'] < 30 else "관망"
            
            # 최종 신호
            final_signal = "매수" if trend_signal == "상승 추세" and buy_signal == "매수 고려" else "보류"
            
            # 손절가
            stop_loss = latest['Close'] * (1 - stop_loss_pct / 100)

            # 결과 색상
            color = "#2ECC71" if final_signal == "매수" else ("#F1C40F" if final_signal == "보류" else "#E74C3C")
            
            return {
                "티커": ticker,
                "신호": final_signal,
                "현재가": latest['Close'],
                "추세": trend_signal,
                "거래량": volume_signal,
                "RSI": latest['RSI'],
                "손절가": stop_loss,
                "컬러": color,
                "차트": df
            }
        
        except Exception as e:
            return {
                "티커": ticker, 
                "신호": "오류", 
                "현재가": 0, 
                "추세": str(e),
                "거래량": "",
                "RSI": 0,
                "손절가": 0,
                "컬러": "#E74C3C",
                "차트": pd.DataFrame()
            }
    
    # --- 병렬 분석 및 결과 표시 ---
    progress_bar = st.progress(0)
    results = []
    total_tickers = len(tickers)

    for i, ticker in enumerate(tickers):
        result = analyze_ticker(ticker)
        if result:
            results.append(result)
        progress_bar.progress((i + 1) / total_tickers)

    # 신호 순으로 정렬 (매수 > 보류 > 오류)
    results.sort(key=lambda x: (x['신호'] != '매수', x['신호'] != '보류', x['신호'] == '오류'))
        
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
            if not res['차트'].empty:
                st.line_chart(res['차트']['Close'][-60:], height=150) # 최근 60일 종가
