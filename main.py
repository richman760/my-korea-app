import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import datetime
import time

st.set_page_config(layout="wide", page_title="🇰🇷 한국 퀀트 스캐너")

# 1. 종목 목록 가져오기 (로직 유지)
def get_all_krx_tickers():
    df_krx = fdr.StockListing('KRX')
    df_filtered = df_krx[
        (df_krx['Market'].isin(['KOSPI', 'KOSDAQ'])) & 
        (~df_krx['Name'].str.contains('우|우B|우C|우선주|스팩|ETF|ETN|정지'))
    ]
    df_filtered = df_filtered.sort_values(by='Marcap', ascending=False)
    return df_filtered[['Code', 'Name']].to_dict('records')

# 2. 형의 백테스트 로직 (로직 유지)
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
        if len(future_df) < hold_days:
            total_signals -= 1
            continue
        entry_price = df.loc[date, 'Close']
        if future_df['High'].max() >= entry_price * (1 + target_profit_pct): success_count += 1
        if future_df['Low'].min() <= entry_price * 0.95: stop_loss_1_count += 1
        if future_df['Low'].min() <= entry_price * 0.90: stop_loss_2_count += 1
            
    if total_signals == 0: return None, None
    
    today_close = int(df['Close'].iloc[-1])
    return {
        'today_close': today_close,
        'target_val': int(today_close * (1 + target_profit_pct)),
        'stop_1_val': int(today_close * 0.95),
        'stop_2_val': int(today_close * 0.90),
        'prob_success': (success_count / total_signals) * 100,
        'prob_stop_1': (stop_loss_1_count / total_signals) * 100,
        'prob_stop_2': (stop_loss_2_count / total_signals) * 100
    }, hold_days

# 3. 화면 UI (형이 원하시는 그 포맷 그대로 출력)
st.title("🇰🇷 한국 퀀트 고확률 종목 스캐너")

if st.button("🚀 스캔 시작"):
    stocks = get_all_krx_tickers()[:500]
    today_str = datetime.datetime.now().strftime('%m월%d일')
    future_date_str = (datetime.datetime.now() + datetime.timedelta(days=12)).strftime('%m월%d일')
    
    found_count = 0
    progress_bar = st.progress(0)
    
    for i, stock in enumerate(stocks):
        res, hold_days = run_backtest_for_stock(stock['Code'])
        progress_bar.progress((i + 1) / len(stocks))
        
        if res and res['prob_success'] >= 80:
            found_count += 1
            # 형이 주신 print문의 그 포맷 그대로 웹에 출력
            st.markdown("---")
            st.write(f"### 종목명 : {stock['Name']}")
            st.write(f"추천 진입가 {today_str} 종가 부근 ({res['today_close']:,}원 내외)")
            st.write(f"당일고가 {res['target_val']:,}원 도달 가능성 **{res['prob_success']:.0f}%**")
            st.write(f"당일종가 < {res['stop_1_val']:,}원 도달 가능성 {res['prob_stop_1']:.0f}%")
            
            if res['prob_stop_2'] < 3:
                st.write(f"당일종가 < {res['stop_2_val']:,}원 도달 가능성 극히 드묾")
            else:
                st.write(f"당일종가 < {res['stop_2_val']:,}원 도달 가능성 {res['prob_stop_2']:.0f}%")
            
            st.caption(f"기한 {future_date_str}까지 (도달하지 않을 시 해당일 종가 매도)")
            st.error(f"{res['today_close']:,}원에 사서 {res['target_val']:,}원에 매도걸어두시면 체결될 가능성 {res['prob_success']:.0f}%라서 추천드려요")

    st.success(f"\n[스캔 완료] 총 {found_count}개 발견!")
