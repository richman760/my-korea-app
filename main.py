import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import datetime

st.set_page_config(layout="wide", page_title="🇰🇷 최종 퀀트 스캐너")

# 숫자 -> 한글 변환 함수 (천만원 표시)
def format_korean(n):
    if n == 0: return "0원"
    units = ["", "만", "억", "조"]
    res = ""
    # 4자리씩 끊어서 처리
    n_str = str(n)
    for i in range(len(n_str) // 4 + 1):
        chunk = n_str[-4*(i+1):] if i == 0 else n_str[-4*(i+1):-4*i]
        if chunk and int(chunk) > 0:
            res = f"{int(chunk)}{units[i]}" + res
    return res + "원"

# 1. 퀀트 로직 (원본 그대로)
def run_backtest_for_stock(ticker_code):
    try:
        df = fdr.DataReader(ticker_code, '2005-01-01')
        if len(df) < 250: return None
        
        df['MA20'] = df['Close'].rolling(window=20).mean()
        df['STD20'] = df['Close'].rolling(window=20).std()
        df['BB_Lower'] = df['MA20'] - (2 * df['STD20'])
        df['RSI'] = 100 - (100 / (1 + (df['Close'].diff().where(df['Close'].diff()>0, 0).rolling(14).mean() / (-df['Close'].diff().where(df['Close'].diff()<0, 0).rolling(14).mean() + 1e-9))))
        df['Vol_MA5'] = df['Volume'].rolling(window=5).mean()
        df['Signal'] = (df['RSI'].rolling(window=3).min() <= 35) & (df['Close'] >= df['BB_Lower'] * 0.98) & (df['Volume'] > df['Vol_MA5'])
        
        if not df['Signal'].iloc[-1]: return None
        
        entry = int(df['Close'].iloc[-1])
        target = int(entry * 1.045)
        stop1 = int(entry * 0.95)
        stop2 = int(entry * 0.90)
        
        signal_days = df[df['Signal'] == True].index[:-1]
        success = stop1_cnt = stop2_cnt = 0
        for d in signal_days:
            sub = df.loc[d:].iloc[1:9]
            if len(sub) < 8: continue
            if sub['High'].max() >= entry * 1.045: success += 1
            if sub['Low'].min() <= entry * 0.95: stop1_cnt += 1
            if sub['Low'].min() <= entry * 0.90: stop2_cnt += 1
            
        return {
            'name': fdr.StockListing('KRX').set_index('Code').loc[ticker_code, 'Name'],
            'today_close': entry, 'target_val': target, 'stop_1_val': stop1, 'stop_2_val': stop2,
            'prob_success': (success / len(signal_days)) * 100 if len(signal_days) > 0 else 0,
            'prob_stop_1': (stop1_cnt / len(signal_days)) * 100 if len(signal_days) > 0 else 0,
            'prob_stop_2': (stop2_cnt / len(signal_days)) * 100 if len(signal_days) > 0 else 0
        }
    except: return None

# 2. UI 구성
st.title("💰 퀀트 스캐너")
budget = st.number_input("투자 자산(원)", value=10000000, step=1000000)
# 형이 원한 숫자 + 한글 표시
st.write(f"### 현재 설정 자산: {budget:,}원 ({format_korean(budget)})")

if st.button("🚀 스캔 시작"):
    st.session_state['results'] = []
    tickers = fdr.StockListing('KRX')[['Code', 'Name']].to_dict('records')
    with st.spinner('스캔 중...'):
        for stock in tickers[:300]: 
            res = run_backtest_for_stock(stock['Code'])
            if res and res['prob_success'] >= 80:
                st.session_state['results'].append(res)
    st.success("스캔 완료!")

# 3. 출력 (형의 원본 멘트 & 계산기 완벽 복원)
today_str = datetime.date.today().strftime('%m월%d일')
future_date_str = (datetime.date.today() + datetime.timedelta(days=12)).strftime('%m월%d일')

if 'results' in st.session_state:
    for res in st.session_state['results']:
        with st.expander(f"📌 {res['name']}", expanded=True):
            st.text(f"종목명 : {res['name']}")
            st.text(f"추천 진입가 {today_str} 종가 부근 ({res['today_close']:,}원 내외)")
            st.text(f"당일고가 {res['target_val']:,}원 도달 가능성 {res['prob_success']:.0f}%")
            st.text(f"당일종가 < {res['stop_1_val']:,}원 도달 가능성 {res['prob_stop_1']:.0f}%")
            
            if res['prob_stop_2'] < 3:
                st.text(f"당일종가 < {res['stop_2_val']:,}원 도달 가능성 극히드묾")
            else:
                st.text(f"당일종가 < {res['stop_2_val']:,}원 도달 가능성 {res['prob_stop_2']:.0f}%")
            st.text(f"기한 {future_date_str}까지")
            
            # 계산기
            shares = budget // res['today_close']
            profit = (res['target_val'] - res['today_close']) * shares
            
            st.markdown("---")
            # 형이 원하는 멘트
            st.markdown(f"**👉 {res['today_close']:,}원에 매수해서 {res['target_val']:,}원에 파세요. 성공률은 {res['prob_success']:.0f}%입니다.**")
            # 금액 표시 (숫자 + 한글)
            st.markdown(f"**💰 {budget:,}원 ({format_korean(budget)}) 투입 시 예상 수익: +{profit:,}원 ({format_korean(profit)}) (매수 수량: {shares:,}주)**")

    # 4. CSV 저장
    df_save = pd.DataFrame(st.session_state['results'])
    csv = df_save.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
    st.download_button("💾 휴대폰에 저장하기 (CSV)", csv, "퀀트결과.csv", "text/csv")
