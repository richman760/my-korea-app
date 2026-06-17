import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

st.set_page_config(layout="wide", page_title="🇰🇷 한국 퀀트 스캐너")

# 1. 숫자 -> 한글 변환 함수
def number_to_korean(n):
    if n == 0: return "0원"
    if n < 10000: return f"{n:,}원"
    man = n // 10000
    remainder = n % 10000
    result = f"{man:,}만"
    if remainder > 0: result += f"{remainder:,}"
    return result + "원"

# 2. 투자 자산 입력 (사이드바)
st.sidebar.title("💰 매매 설정")
budget = st.sidebar.number_input("투자 가능 자산 (원)", value=10000000, step=1000000)
st.sidebar.caption(f"현재 설정: {number_to_korean(budget)}")

# 3. 기억력 장치 (결과 유지용)
if 'found_list' not in st.session_state:
    st.session_state['found_list'] = []

# 4. 퀀트 로직
def run_backtest_for_stock(ticker_code, target_profit_pct=0.045):
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
        
        entry_price = df['Close'].iloc[-1]
        signal_days = df[df['Signal'] == True].index[:-1]
        success_count = stop_1_count = 0
        for d in signal_days:
            sub = df.loc[d:].iloc[1:9]
            if len(sub) < 8: continue
            if sub['High'].max() >= entry_price * (1 + target_profit_pct): success_count += 1
            if sub['Low'].min() <= entry_price * 0.95: stop_1_count += 1
        
        return {
            'name': fdr.StockListing('KRX').set_index('Code').loc[ticker_code, 'Name'],
            'today_close': int(entry_price),
            'target_val': int(entry_price * (1 + target_profit_pct)),
            'stop_1_val': int(entry_price * 0.95),
            'prob_success': (success_count / len(signal_days)) * 100,
            'prob_stop_1': (stop_1_count / len(signal_days)) * 100
        }
    except:
        return None

# 5. 스캔 버튼 및 실행
if st.button("🚀 스캔 시작"):
    st.session_state['found_list'] = []
    with st.spinner('종목 스캔 중... 잠시만 기다려주세요!'):
        try:
            # KRX 종목을 여기서 안전하게 불러옴
            df_krx = fdr.StockListing('KRX')
            tickers = df_krx[(df_krx['Market'].isin(['KOSPI', 'KOSDAQ'])) & (~df_krx['Name'].str.contains('우|우B|우C|우선주|스팩|ETF|ETN|정지'))]['Code'].tolist()[:300]
            
            bar = st.progress(0)
            for i, code in enumerate(tickers):
                res = run_backtest_for_stock(code)
                bar.progress((i + 1) / len(tickers))
                if res and res['prob_success'] >= 80:
                    st.session_state['found_list'].append(res)
            bar.empty()
        except Exception as e:
            st.error(f"서버 접속 오류 발생! 잠시 후 다시 눌러주세요: {e}")

# 6. 결과 출력
today_str = datetime.date.today().strftime('%Y-%m-%d')
for res in st.session_state['found_list']:
    with st.expander(f"📌 {res['name']}", expanded=True):
        st.text(f"종목명 : {res['name']}")
        st.text(f"추천 진입가 {today_str} 종가 부근 ({res['today_close']:,}원)")
        st.text(f"목표가 {res['target_val']:,}원 (승률 {res['prob_success']:.0f}%)")
        st.text(f"손절가 < {res['stop_1_val']:,}원 (손절가능성 {res['prob_stop_1']:.0f}%)")
        
        shares = budget // res['today_close']
        profit = (res['target_val'] - res['today_close']) * shares
        st.write("---")
        st.markdown(f"**💰 투자 시뮬레이션**")
        st.markdown(f"**👉 {budget:,}원({number_to_korean(budget)}) 투입 시**")
        st.markdown(f"**예상 매수수량: {shares:,}주 | 목표가 도달 시 예상수익: +{profit:,}원**")
        st.text("=" * 50)

# 7. 구글 시트 저장
if st.session_state['found_list'] and st.button("💾 구글 시트에 저장하기"):
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gsheets"], scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_url(st.secrets["sheet_url"]).sheet1
        rows = [[today_str, r['name'], f"{r['today_close']:,}원", f"{r['target_val']:,}원", f"{budget:,}원", f"{((r['target_val'] - r['today_close']) * (budget // r['today_close'])):,}원"] for r in st.session_state['found_list']]
        sheet.append_rows(rows)
        st.success("구글 시트에 저장 완료!")
    except Exception as e:
        st.error(f"저장 실패: {e}")
