import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import datetime
import gspread
from google.oauth2 import service_account

st.set_page_config(layout="wide", page_title="🇰🇷 퀀트 테스트 모드")

# 기억력 장치
if 'found_list' not in st.session_state: st.session_state['found_list'] = []

# 퀀트 로직 (기존과 동일)
def run_backtest_for_stock(ticker_code):
    try:
        df = fdr.DataReader(ticker_code, '2005-01-01')
        if len(df) < 250: return None
        df['MA20'] = df['Close'].rolling(20).mean()
        df['BB_Lower'] = df['MA20'] - (2 * df['Close'].rolling(20).std())
        df['RSI'] = 100 - (100 / (1 + (df['Close'].diff().clip(0).rolling(14).mean() / (-df['Close'].diff().clip(upper=0).rolling(14).mean() + 1e-9))))
        df['Signal'] = (df['RSI'].rolling(3).min() <= 35) & (df['Close'] >= df['BB_Lower'] * 0.98)
        if not df['Signal'].iloc[-1]: return None
        return {'name': fdr.StockListing('KRX').set_index('Code').loc[ticker_code, 'Name'], 
                'close': int(df['Close'].iloc[-1]), 'target': int(df['Close'].iloc[-1] * 1.045)}
    except: return None

st.title("🧪 디버깅 테스트 모드")
if st.button("🚀 10개 종목 테스트 스캔"):
    st.session_state['found_list'] = []
    # [핵심] 여기서 300개를 다 안 돌리고 딱 10개만 돌림
    tickers = fdr.StockListing('KRX')['Code'].tolist()[:10] 
    with st.spinner('테스트 중...'):
        for code in tickers:
            res = run_backtest_for_stock(code)
            if res: st.session_state['found_list'].append(res)
    st.write(f"스캔 완료! 발견된 종목: {len(st.session_state['found_list'])}개")

# 결과 출력
for res in st.session_state['found_list']:
    st.write(f"종목: {res['name']} | 진입가: {res['close']:,}원")

# 7. 구글 시트 저장 (테스트)
if st.session_state['found_list'] and st.button("💾 구글 시트에 저장하기"):
    try:
        creds = service_account.Credentials.from_service_account_info(
            st.secrets["gsheets"], scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        client = gspread.authorize(creds)
        sheet = client.open_by_url(st.secrets["sheet_url"]).sheet1
        rows = [[str(datetime.date.today()), r['name'], f"{r['close']:,}원"] for r in st.session_state['found_list']]
        sheet.append_rows(rows)
        st.success("저장 완료!")
    except Exception as e:
        st.error(f"저장 실패 에러 메시지: {str(e)}")
