import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import datetime
import time

st.set_page_config(layout="wide", page_title="🇰🇷 한국 퀀트 스캐너")

# 1. 종목 목록 가져오기 (캐싱)
@st.cache_data
def get_all_krx_tickers():
    df_krx = fdr.StockListing('KRX')
    df_filtered = df_krx[
        (df_krx['Market'].isin(['KOSPI', 'KOSDAQ'])) & 
        (~df_krx['Name'].str.contains('우|우B|우C|우선주|스팩|ETF|ETN|정지'))
    ]
    df_filtered = df_filtered.sort_values(by='Marcap', ascending=False)
    return df_filtered[['Code', 'Name']].to_dict('records')

# 2. 백테스트 엔진
def run_backtest(ticker_code, target_profit_pct=0.045, hold_days=8):
    try:
        df = fdr.DataReader(ticker_code, (datetime.datetime.now() - datetime.timedelta(days=365)).strftime('%Y-%m-%d'))
        if len(df) < 50: return None
        
        df['MA20'] = df['Close'].rolling(window=20).mean()
        df['STD20'] = df['Close'].rolling(window=20).std()
        df['BB_Lower'] = df['MA20'] - (2 * df['STD20'])
        
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / (loss + 1e-9)
        df['RSI'] = 100 - (100 / (1 + rs))
        
        df['Vol_MA5'] = df['Volume'].rolling(window=5).mean()
        df['Signal'] = (df['RSI'].rolling(window=3).min() <= 35) & \
                       (df['Close'] >= df['BB_Lower'] * 0.98) & \
                       (df['Volume'] > df['Vol_MA5'])
        
        if not df['Signal'].iloc[-1]: return None
        
        # 간단 확률 계산 (백테스트)
        signal_days = df[df['Signal'] == True].index[:-1]
        if len(signal_days) < 5: return None
        
        success_count = 0
        for date in signal_days:
            future = df.loc[date:].iloc[1:hold_days+1]
            if len(future) < hold_days: continue
            if future['High'].max() >= df.loc[date, 'Close'] * (1 + target_profit_pct):
                success_count += 1
        
        return (success_count / len(signal_days)) * 100
    except: return None

# 3. 화면 UI
st.title("🇰🇷 한국 퀀트 고확률 종목 스캐너")
st.warning("⚠️ 500개 종목을 분석하므로 '스캔 시작' 버튼을 누르고 잠시만 기다려주세요!")

if st.button("🚀 스캔 시작"):
    stocks = get_all_krx_tickers()[:500] # 상위 500개
    results = []
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, stock in enumerate(stocks):
        status_text.text(f"분석 중... {stock['Name']} ({i+1}/{len(stocks)})")
        prob = run_backtest(stock['Code'])
        
        if prob and prob >= 80:
            results.append({"종목명": stock['Name'], "코드": stock['Code'], "승률": f"{prob:.1f}%"})
            
        progress_bar.progress((i + 1) / len(stocks))
    
    status_text.text("분석 완료!")
    
    if results:
        st.success(f"총 {len(results)}개의 추천 종목을 찾았습니다!")
        st.table(pd.DataFrame(results))
    else:
        st.info("조건을 만족하는 종목이 없습니다.")
