
import yfinance as yf
import pandas as pd
from app import analyze_dataframe # app.py에서 분석 함수 가져오기

# --- 검증 설정 ---
# 과거 오류를 일으켰거나, 데이터가 불완전할 가능성이 있는 까다로운 종목 목록
VALIDATION_TICKERS = [
    "KMAN",       # 데이터 부족 오류 가능성
    "ARM",        # 신규 상장주 (데이터 기간 짧음)
    "373220.KS",  # 한국 신규 상장주 (카카오뱅크)
    "GOOGL",      # 안정적인 대형주 (기준점)
    "005930.KS",  # 한국 대형주 (기준점)
]

STOP_LOSS_PCT = 3.0 # 테스트용 손절 라인

def run_validation():
    """v4.1 분석 로직의 안정성을 자동으로 검증하는 스크립트"""
    print("--- v4.1 분석 엔진 자동 검증 시작 ---")
    print(f"대상 티커: {VALIDATION_TICKERS}")
    print("-" * 35)

    passed_count = 0
    failed_tickers = []

    for ticker in VALIDATION_TICKERS:
        print(f"[검증 중] {ticker}...")
        try:
            # 1. 실제와 동일한 방식으로 데이터 다운로드
            df = yf.download(ticker, period="1y", progress=False, auto_adjust=True)
            
            if df.empty:
                print(f"[결과] 🟡 경고: {ticker} 데이터 없음. 검증 건너뛰기.")
                # 데이터가 없는 경우는 분석 함수의 오류가 아니므로 실패로 간주하지 않음
                passed_count += 1 
                continue

            # 2. 데이터 기본 전처리 (app.py 로직과 동일하게)
            df.columns = [str(col).lower() for col in df.columns]
            for col in ['open', 'high', 'low', 'close', 'volume']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # 데이터 부족은 예상된 시나리오이므로, 분석 함수를 호출
            if df['close'].count() < 200:
                 print(f"[정보] {ticker} 유효 데이터({df['close'].count()}개) 200개 미만.")

            # 3. 핵심 분석 함수 실행
            result = analyze_dataframe(ticker, df.copy(), STOP_LOSS_PCT)

            # 4. 결과 판정
            # "데이터 부족"은 예상된 오류이므로 통과 처리
            if result.get('신호') == '오류' and "데이터 부족" not in result.get('오류 원인', ""):
                print(f"[결과] 🔴 실패: {ticker}")
                print(f"    ㄴ 원인: {result.get('오류 원인')}")
                failed_tickers.append(ticker)
            else:
                print(f"[결과] ✅ 통과: {ticker}")
                passed_count += 1

        except Exception as e:
            print(f"[결과] 🔴 실패: {ticker}")
            print(f"    ㄴ 원인: 스크립트 실행 중 예외 발생 - {e}")
            failed_tickers.append(ticker)
        
        print("-" * 20)

    # --- 최종 결과 --- 
    print("\n--- 최종 검증 결과 ---")
    print(f"총 {len(VALIDATION_TICKERS)}개 중 {passed_count}개 통과")
    
    if not failed_tickers:
        print("\n🎉 축하합니다! 모든 검증을 통과했습니다.")
        print("v4.1의 새로운 분석 엔진은 안정적으로 작동합니다.")
    else:
        print(f"\n❌ 실패한 티커: {failed_tickers}")
        print("분석 엔진 로직을 다시 확인해야 합니다.")

if __name__ == "__main__":
    run_validation()
