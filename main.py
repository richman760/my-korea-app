import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import datetime
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(layout="wide", page_title="🇰🇷 한국 퀀트 스캐너")

# 1. 숫자 -> 한글 변환
def number_to_korean(n):
    if n == 0: return "0원"
    if n < 10000: return f"{n:,}원"
    man = n // 10000
    remainder = n % 10000
    result = f"{man:,}만"
    if remainder > 0: result += f"{remainder:,}"
    return result + "원"

# 2. 기억력 장치
if 'found_list' not in st.session_state:
    st.session_state['found_list'] = []

# 3. 사이드바 (투자금 입력)
st.sidebar.title("💰 매매 설정")
budget = st.sidebar.number_input("투자 가능 자산 (원)", value=10000000, step=1000000)
st.sidebar.caption(f"현재 설정: {number_to_korean(budget)}")

# 4. 퀀트 로직
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
        
        # 승률 계산 로직
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
            'prob_success': (success / len(signal_days)) * 100,
            'prob_stop_1': (stop1_cnt / len(signal_days)) * 100,
            'prob_stop_2': (stop2_cnt / len(signal_days)) * 100
        }
    except: return None

# 5. 스캔 버튼
if st.button("🚀 스캔 시작"):
    st.session_state['found_list'] = []
    with st.spinner('스캔 중...'):
        tickers = fdr.StockListing('KRX')['Code'].tolist()[:300]
        for code in tickers:
            res = run_backtest_for_stock(code)
            if res: st.session_state['found_list'].append(res)

# 6. 결과 출력 (형이 원하던 그 포맷!)
today_str = datetime.date.today().strftime('%Y-%m-%d')
future_date_str = (datetime.date.today() + datetime.timedelta(days=8)).strftime('%Y-%m-%d')

for res in st.session_state['found_list']:
    with st.expander(f"📌 {res['name']}", expanded=True):
        st.text(f"종목명 : {res['name']}")
        st.text(f"추천 진입가 {today_str} 종가 부근 ({res['today_close']:,}원 내외)")
        st.text(f"당일고가 {res['target_val']:,}원 도달 가능성 {res['prob_success']:.0f}%")
        st.text(f"당일종가 < {res['stop_1_val']:,}원 도달 가능성 {res['prob_stop_1']:.0f}%")
        if res['prob_stop_2'] < 3: st.text(f"당일종가 < {res['stop_2_val']:,}원 도달 가능성 극히드묾")
        else: st.text(f"당일종가 < {res['stop_2_val']:,}원 도달 가능성 {res['prob_stop_2']:.0f}%")
        st.text(f"기한 {future_date_str}까지")
        
        shares = budget // res['today_close']
        profit = (res['target_val'] - res['today_close']) * shares
        st.write("---")
        st.markdown(f"**💰 {res['today_close']:,}원에 사서 {res['target_val']:,}원에 매도 시**")
        st.markdown(f"**👉 {budget:,}원({number_to_korean(budget)}) 투입 시 예상 수익: +{profit:,}원 (매수 수량: {shares:,}주)**")
        st.text("=" * 50)

# 7. 구글 시트 저장 (메모리 인증으로 PermissionError 차단)
if st.session_state['found_list'] and st.button("💾 구글 시트에 저장하기"):
    try:
        creds = Credentials.from_service_account_info(st.secrets["gsheets"])
        client = gspread.authorize(creds)
        sheet = client.open_by_url(st.secrets["sheet_url"]).sheet1
        
        rows = [[str(datetime.date.today()), r['name'], f"{r['today_close']:,}원", f"{r['target_val']:,}원", f"{budget:,}원"] for r in st.session_state['found_list']]
        sheet.append_rows(rows)
        st.success("저장 완료!")
    except Exception as e:
        st.error(f"저장 실패: {str(e)}")
