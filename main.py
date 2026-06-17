import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

st.set_page_config(layout="wide", page_title="🇰🇷 한국 퀀트 스캐너")

# 1. 종목 목록
def get_all_krx_tickers():
    df_krx = fdr.StockListing('KRX')
    df_filtered = df_krx[
        (df_krx['Market'].isin(['KOSPI', 'KOSDAQ'])) & 
        (~df_krx['Name'].str.contains('우|우B|우C|우선주|스팩|ETF|ETN|정지'))
    ]
    return df_filtered[['Code', 'Name']].to_dict('records')

# 2. 퀀트 로직
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
    df['Signal'] = (df['RSI'].rolling(window=3).min() <= 35) & (df['Close'] >= df['BB_Lower'] * 0.98) & (df['Volume'] > df['Vol_MA5'])
    
    if not df['Signal'].iloc[-1]: return None, None
    
    signal_days = df[df['Signal'] == True].index[:-1]
    success_count = 0
    for date in signal_days:
        future_df = df.loc[date:].iloc[1:hold_days+1]
        if len(future_df) < hold_days: continue
        if future_df['High'].max() >= df.loc[date, 'Close'] * (1 + target_profit_pct): success_count += 1
    
    return {'today_close': int(df['Close'].iloc[-1]), 'target_val': int(df['Close'].iloc[-1] * (1 + target_profit_pct)), 'prob_success': (success_count / len(signal_days)) * 100}, hold_days

# 3. UI 및 시트 저장 기능
st.title("🇰🇷 한국 퀀트 고확률 종목 스캐너")
budget = st.sidebar.number_input("투자 가능 금액 (원)", value=1000000, step=100000)

if st.button("🚀 스캔 시작"):
    stocks = get_all_krx_tickers()[:500]
    found_list = []
    bar = st.progress(0)
    for i, stock in enumerate(stocks):
        res, _ = run_backtest_for_stock(stock['Code'])
        bar.progress((i + 1) / len(stocks))
        if res and res['prob_success'] >= 80:
            found_list.append({"날짜": str(datetime.date.today()), "종목명": stock['Name'], "진입가": res['today_close'], "목표가": res['target_val'], "투자금": budget, "예상수익": int((res['target_val'] - res['today_close']) * (budget // res['today_close']))})
    
    if found_list:
        df_final = pd.DataFrame(found_list)
        st.table(df_final)
        
        if st.button("💾 구글 시트에 저장하기"):
            scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
            creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gsheets"], scope)
            client = gspread.authorize(creds)
            sheet = client.open_by_url(st.secrets["sheet_url"]).sheet1
            sheet.append_rows(df_final.values.tolist())
            st.success("구글 시트에 저장 완료!")
