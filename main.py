import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import datetime
import gspread
from google.oauth2 import service_account

# 1. 숫자 -> 한글 변환
def number_to_korean(n):
    if n < 10000: return f"{n:,}원"
    man = n // 10000
    remainder = n % 10000
    return f"{man:,}만{f'{remainder:,}' if remainder > 0 else ''}원"

# 2. 형이 올린 한국_퀀트.py의 핵심 로직
def run_backtest_for_stock(ticker_code, target_profit_pct=0.045, hold_days=8):
    try:
        df = fdr.DataReader(ticker_code, '2005-01-01')
        if len(df) < 250: return None, None
        
        # 지표 계산
        df['MA20'] = df['Close'].rolling(window=20).mean()
        df['STD20'] = df['Close'].rolling(window=20).std()
        df['BB_Lower'] = df['MA20'] - (2 * df['STD20'])
        
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        df['RSI'] = 100 - (100 / (1 + (gain / (loss + 1e-9))))
        
        df['Vol_MA5'] = df['Volume'].rolling(window=5).mean()
        df['당일등락'] = df['Close'].pct_change() * 100
        
        # 형의 핵심 조건
        cond_rsi = df['RSI'].rolling(window=3).min() <= 35
        cond_bb = df['Close'] >= df['BB_Lower'] * 0.98
        cond_vol = df['Volume'] > df['Vol_MA5']
        cond_price = df['당일등락'] > -1
        df['Signal'] = cond_rsi & cond_bb & cond_vol & cond_price
        
        if not df['Signal'].iloc[-1]: return None, None
            
        # 확률 계산
        signal_days = df[df['Signal'] == True].index[:-1]
        success = stop1 = stop2 = 0
        for d in signal_days:
            sub = df.loc[d:].iloc[1:hold_days+1]
            if len(sub) < hold_days: continue
            if sub['High'].max() >= df.loc[d, 'Close'] * (1 + target_profit_pct): success += 1
            if sub['Low'].min() <= df.loc[d, 'Close'] * 0.95: stop1 += 1
            if sub['Low'].min() <= df.loc[d, 'Close'] * 0.90: stop2 += 1
            
        total = len(signal_days)
        return {
            'today_close': int(df['Close'].iloc[-1]),
            'target_val': int(df['Close'].iloc[-1] * (1 + target_profit_pct)),
            'stop_1_val': int(df['Close'].iloc[-1] * 0.95),
            'stop_2_val': int(df['Close'].iloc[-1] * 0.90),
            'prob_success': (success / total) * 100,
            'prob_stop_1': (stop1 / total) * 100,
            'prob_stop_2': (stop2 / total) * 100
        }, hold_days
    except: return None, None

# UI 구성
st.set_page_config(layout="wide")
st.title("🚀 한국 퀀트 스캐너")
budget = st.sidebar.number_input("투자 자산(원)", value=10000000)
st.sidebar.write(f"현재: {number_to_korean(budget)}")

if st.button("스캔 시작"):
    st.session_state['results'] = []
    tickers = fdr.StockListing('KRX')[['Code', 'Name']].to_dict('records')[:300]
    for stock in tickers:
        res, _ = run_backtest_for_stock(stock['Code'])
        if res and res['prob_success'] >= 80:
            res['name'] = stock['Name']
            st.session_state['results'].append(res)

# 결과 출력
for r in st.session_state.get('results', []):
    with st.expander(f"📌 {r['name']}", expanded=True):
        st.text(f"진입가: {r['today_close']:,}원 | 목표가: {r['target_val']:,}원")
        st.text(f"승률: {r['prob_success']:.0f}% | 손절가능성: {r['prob_stop_1']:.0f}%")
        shares = budget // r['today_close']
        profit = (r['target_val'] - r['today_close']) * shares
        st.markdown(f"**👉 투입 시 예상수익: +{profit:,}원 ({shares:,}주)**")

# 저장 로직 (에러 원천 차단)
if st.button("💾 구글 시트 저장"):
    try:
        SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
        creds = service_account.Credentials.from_service_account_info(st.secrets["gsheets"], scopes=SCOPES)
        client = gspread.authorize(creds)
        sheet = client.open_by_url(st.secrets["sheet_url"]).sheet1
        rows = [[str(datetime.date.today()), r['name'], f"{r['today_close']:,}원"] for r in st.session_state['results']]
        sheet.append_rows(rows)
        st.success("저장 완료!")
    except Exception as e: st.error(f"저장 오류: {e}")
