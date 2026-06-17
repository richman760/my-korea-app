import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- 숫자 -> 한글 변환 함수 ---
def number_to_korean(n):
    if n == 0: return "0원"
    if n < 10000: return f"{n:,}원"
    
    man = n // 10000
    remainder = n % 10000
    
    result = f"{man:,}만"
    if remainder > 0:
        result += f"{remainder:,}"
    return result + "원"

st.set_page_config(layout="wide", page_title="🇰🇷 한국 퀀트 스캐너")

# 1. 자산 입력 (사이드바)
st.sidebar.title("💰 매매 설정")
budget = st.sidebar.number_input("투자 가능 자산 (원)", value=10000000, step=1000000)
# 한글 표기 (천만원 등)
st.sidebar.caption(f"현재 설정: {number_to_korean(budget)}")

# 2. 기억력 장치 (결과 유지)
if 'found_list' not in st.session_state:
    st.session_state['found_list'] = []

# 3. 퀀트 로직
def run_backtest_for_stock(ticker_code, target_profit_pct=0.045):
    df = fdr.DataReader(ticker_code, '2005-01-01')
    if len(df) < 250: return None
    
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['STD20'] = df['Close'].rolling(window=20).std()
    df['BB_Lower'] = df['MA20'] - (2 * df['STD20'])
    df['RSI'] = 100 - (100 / (1 + (df['Close'].diff().where(df['Close'].diff()>0, 0).rolling(14).mean() / (-df['Close'].diff().where(df['Close'].diff()<0, 0).rolling(14).mean() + 1e-9))))
    df['Vol_MA5'] = df['Volume'].rolling(window=5).mean()
    df['Signal'] = (df['RSI'].rolling(window=3).min() <= 35) & (df['Close'] >= df['BB_Lower'] * 0.98) & (df['Volume'] > df['Vol_MA5'])
    
    if not df['Signal'].iloc[-1]: return None
    
    entry_price = df['Close'].iloc[-1]
    signal_days = df[df['Signal'] == True].index[:-1]
    success_count = stop_1_count = stop_2_count = 0
    
    for d in signal_days:
        sub = df.loc[d:].iloc[1:9]
        if len(sub) < 8: continue
        if sub['High'].max() >= df.loc[d, 'Close'] * (1 + target_profit_pct): success_count += 1
        if sub['Low'].min() <= df.loc[d, 'Close'] * 0.95: stop_1_count += 1
        if sub['Low'].min() <= df.loc[d, 'Close'] * 0.90: stop_2_count += 1
    
    return {
        'name': fdr.StockListing('KRX').set_index('Code').loc[ticker_code, 'Name'],
        'today_close': int(entry_price),
        'target_val': int(entry_price * (1 + target_profit_pct)),
        'stop_1_val': int(entry_price * 0.95),
        'stop_2_val': int(entry_price * 0.90),
        'prob_success': (success_count / len(signal_days)) * 100,
        'prob_stop_1': (stop_1_count / len(signal_days)) * 100,
        'prob_stop_2': (stop_2_count / len(signal_days)) * 100
    }

# 4. 스캔 및 결과
if st.button("🚀 스캔 시작"):
    st.session_state['found_list'] = []
    tickers = fdr.StockListing('KRX')['Code'].tolist()[:500] 
    bar = st.progress(0)
    for i, code in enumerate(tickers):
        res = run_backtest_for_stock(code)
        bar.progress((i + 1) / len(tickers))
        if res and res['prob_success'] >= 80:
            st.session_state['found_list'].append(res)
    bar.empty()

# 결과 출력 (상세 포맷)
today_str = datetime.date.today().strftime('%Y-%m-%d')
future_date_str = (datetime.date.today() + datetime.timedelta(days=8)).strftime('%Y-%m-%d')

for res in st.session_state['found_list']:
    with st.expander(f"📌 {res['name']}", expanded=True):
        st.text(f"종목명 : {res['name']}")
        st.text(f"추천 진입가 {today_str} 종가 부근 ({res['today_close']:,}원 내외)")
        st.text(f"당일고가 {res['target_val']:,}원 도달 가능성 {res['prob_success']:.0f}%")
        st.text(f"당일종가 < {res['stop_1_val']:,}원 도달 가능성 {res['prob_stop_1']:.0f}%")
        st.text(f"기한 {future_date_str}까지")
        
        # 계산 로직
        shares = budget // res['today_close']
        profit = (res['target_val'] - res['today_close']) * shares
        st.write(f"---")
        st.markdown(f"**💰 {res['today_close']:,}원에 사서 {res['target_val']:,}원에 매도 시**")
        st.markdown(f"**👉 {budget:,}원 투입 시 예상 수익: +{profit:,}원 (매수 수량: {shares:,}주)**")
        st.text("=" * 50)

# 구글 시트 저장
if st.session_state['found_list'] and st.button("💾 구글 시트에 저장하기"):
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gsheets"], scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_url(st.secrets["sheet_url"]).sheet1
    
    # 저장할 데이터 리스트 만들기
    rows = []
    for res in st.session_state['found_list']:
        shares = budget // res['today_close']
        profit = (res['target_val'] - res['today_close']) * shares
        rows.append([today_str, res['name'], f"{res['today_close']:,}원", f"{res['target_val']:,}원", f"{budget:,}원", f"{profit:,}원"])
    
    sheet.append_rows(rows)
    st.success("구글 시트에 저장 완료!")
