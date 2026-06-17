import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import datetime
from streamlit_gsheets import GSheetsConnection

st.set_page_config(layout="wide", page_title="🇰🇷 한국 퀀트 스캐너")

# 1. 종목 목록 로직
def get_all_krx_tickers():
    df_krx = fdr.StockListing('KRX')
    df_filtered = df_krx[
        (df_krx['Market'].isin(['KOSPI', 'KOSDAQ'])) & 
        (~df_krx['Name'].str.contains('우|우B|우C|우선주|스팩|ETF|ETN|정지'))
    ]
    df_filtered = df_filtered.sort_values(by='Marcap', ascending=False)
    return df_filtered[['Code', 'Name']].to_dict('records')

# 2. 형의 백테스트 로직 (원본 100% 동일)
def run_backtest_for_stock(ticker_code, target_profit_pct=0.045, hold_days=8):
    df = fdr.DataReader(ticker_code, '2005-01-01')
    if len(df) < 250: return None, None
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
    
    if not df['Signal'].iloc[-1]: return None, None
    signal_days = df[df['Signal'] == True].index[:-1]
    total_signals = len(signal_days)
    if total_signals < 5: return None, None
    
    success_count = stop_loss_1_count = stop_loss_2_count = 0
    for date in signal_days:
        future_df = df.loc[date:].iloc[1:hold_days+1]
        if len(future_df) < hold_days: continue
        entry_price = df.loc[date, 'Close']
        if future_df['High'].max() >= entry_price * (1 + target_profit_pct): success_count += 1
        if future_df['Low'].min() <= entry_price * 0.95: stop_loss_1_count += 1
        if future_df['Low'].min() <= entry_price * 0.90: stop_loss_2_count += 1
            
    today_close = int(df['Close'].iloc[-1])
    return {
        'today_close': today_close,
        'target_val': int(today_close * (1 + target_profit_pct)),
        'prob_success': (success_count / total_signals) * 100
    }, hold_days

# 3. UI 및 계산기
st.title("🇰🇷 한국 퀀트 고확률 종목 스캐너")
budget = st.sidebar.number_input("투자 가능 금액 (원)", value=1000000, step=100000)

if st.button("🚀 스캔 시작"):
    stocks = get_all_krx_tickers()[:500]
    found_list = []
    progress_bar = st.progress(0)
    
    for i, stock in enumerate(stocks):
        res, _ = run_backtest_for_stock(stock['Code'])
        progress_bar.progress((i + 1) / len(stocks))
        if res and res['prob_success'] >= 80:
            found_list.append({
                "날짜": datetime.datetime.now().strftime('%Y-%m-%d'),
                "종목명": stock['Name'],
                "진입가": res['today_close'],
                "목표가": res['target_val'],
                "투자금": budget,
                "예상수익": int((res['target_val'] - res['today_close']) * (budget // res['today_close']))
            })
            
    if found_list:
        df_final = pd.DataFrame(found_list)
        st.table(df_final)
        
        # 구글 시트 저장 버튼
        conn = st.connection("gsheets", type=GSheetsConnection)
        if st.button("💾 구글 시트에 저장하기"):
            conn.update(worksheet="시트1", data=df_final)
            st.success("구글 시트에 저장되었습니다!")
