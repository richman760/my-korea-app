import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import datetime
import time

st.set_page_config(layout="wide", page_title="🇰🇷 최종 퀀트 스캐너")

# 숫자 -> 한글 변환
def format_korean(n):
    if n == 0: return "0원"
    units = ["", "만", "억", "조"]
    res = ""
    n_str = str(int(n))
    for i in range(len(n_str) // 4 + 1):
        chunk = n_str[-4*(i+1):] if i == 0 else n_str[-4*(i+1):-4*i]
        if chunk and int(chunk) > 0:
            res = f"{int(chunk)}{units[i]}" + res
    return res + "원"

# [핵심] KRX 서버 차단 방지 (캐싱)
@st.cache_data(ttl=3600)
def get_ticker_list():
    for _ in range(3): 
        try:
            df = fdr.StockListing('KRX')
            return df[['Code', 'Name']].to_dict('records')
        except Exception:
            time.sleep(1)
    return None

# 1. 퀀트 로직
def run_backtest_for_stock(ticker_code, ticker_name): 
    try:
        df = fdr.DataReader(ticker_code, '2005-01-01')
        if len(df) < 250: return None
        
        df['MA20'] = df['Close'].rolling(window=20).mean()
        df['STD20'] = df['Close'].rolling(window=20).std()
        df['BB_Lower'] = df['MA20'] - (2 * df['STD20'])
        
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / (loss + 1e-9)
        df['RSI'] = 100 - (100 / (1 + rs))
        
        df['Vol_MA5'] = df['Volume'].rolling(window=5).mean()
        df['당일등락'] = df['Close'].pct_change() * 100
        
        cond_rsi = df['RSI'].rolling(window=3).min() <= 35
        cond_bb = df['Close'] >= df['BB_Lower'] * 0.98
        cond_vol = df['Volume'] > df['Vol_MA5']
        cond_price = df['당일등락'] > -1
        
        df['Signal'] = cond_rsi & cond_bb & cond_vol & cond_price
        
        if not df['Signal'].iloc[-1]: return None
        
        entry = int(df['Close'].iloc[-1])
        target = int(entry * 1.045)
        stop1 = int(entry * 0.95)
        stop2 = int(entry * 0.90)
        
        signal_days = df[df['Signal'] == True].index[:-1]
        if len(signal_days) == 0: return None
        
        success = stop1_cnt = stop2_cnt = 0
        for d in signal_days:
            sub = df.loc[d:].iloc[1:9]
            if len(sub) < 8: continue
            if sub['High'].max() >= target: success += 1
            if sub['Low'].min() <= stop1: stop1_cnt += 1
            if sub['Low'].min() <= stop2: stop2_cnt += 1
            
        return {
            'name': ticker_name, 
            'today_close': entry, 'target_val': target, 'stop_1_val': stop1, 'stop_2_val': stop2,
            'prob_success': (success / len(signal_days)) * 100,
            'prob_stop_1': (stop1_cnt / len(signal_days)) * 100,
            'prob_stop_2': (stop2_cnt / len(signal_days)) * 100
        }
    except: return None

# 2. UI 구성
st.title("💰 퀀트 스캐너")
budget = st.number_input("투자 자산(원)", value=10000000, step=1000000)
st.write(f"### 현재 설정 자산: {budget:,}원 ({format_korean(budget)})")

if st.button("🚀 스캔 시작"):
    st.session_state['results'] = []
    tickers = get_ticker_list()
    
    if not tickers:
        st.error("⚠️ 한국거래소(KRX) 서버가 붐벼서 연결되지 않았습니다. 잠시 후 버튼을 다시 눌러주세요.")
    else:
        with st.spinner('스캔 중...'):
            for stock in tickers[:300]: 
                res = run_backtest_for_stock(stock['Code'], stock['Name'])
                if res and res['prob_success'] >= 80:
                    st.session_state['results'].append(res)
