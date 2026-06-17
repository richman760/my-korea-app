import streamlit as st
import datetime
import gspread

st.set_page_config(layout="wide", page_title="최종 안정화 테스트")

# 데이터 생성
def get_mock_data():
    return [
        {'name': '삼성전자', 'close': 70000, 'target': 73150},
        {'name': 'SK하이닉스', 'close': 150000, 'target': 156750}
    ]

st.title("🧪 PermissionError 원천 차단 테스트")

if 'results' not in st.session_state: st.session_state['results'] = []

if st.button("🚀 데이터 생성"):
    st.session_state['results'] = get_mock_data()
    st.success("데이터 생성 완료!")

# 결과 출력 (KeyError 방지를 위해 .get() 사용)
for r in st.session_state['results']:
    st.write(f"📌 {r.get('name', '이름없음')} | 진입가: {r.get('close', 0):,}원")

# 저장 로직 (가장 중요한 부분!)
if st.button("💾 구글 시트 저장"):
    if not st.session_state['results']:
        st.error("데이터를 먼저 생성해주세요!")
    else:
        try:
            # 1. 시트 URL 확인
            if "sheet_url" not in st.secrets:
                st.error("Secrets에 sheet_url이 없습니다.")
                st.stop()

            # 2. 핵심: [메모리 전용] 인증 방식 사용
            # 이 방식은 파일 시스템을 건드리지 않아서 PermissionError가 안 납니다.
            client = gspread.service_account_from_dict(st.secrets["gsheets"])
            
            # 3. 시트 접근
            sheet = client.open_by_url(st.secrets["sheet_url"]).sheet1
            
            # 4. 저장
            rows = [[str(datetime.date.today()), r.get('name', ''), f"{r.get('close', 0):,}원"] for r in st.session_state['results']]
            sheet.append_rows(rows)
            st.success("🎉 저장 성공! 드디어 해결되었습니다!")
            
        except Exception as e:
            st.error(f"저장 실패 이유: {type(e).__name__} | 내용: {str(e)}")
