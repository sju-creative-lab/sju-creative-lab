import streamlit as st

# 1. 웹페이지 기본 설정 (웹 브라우저 탭 이름과 아이콘)
st.set_page_config(page_title="AI 서정 실험실", page_icon="🧪", layout="wide")

# 2. 메인 타이틀 및 텍스트
st.title("🧪 AI 서정 실험실 첫 대시보드")
st.subheader("환영합니다! 드디어 첫 번째 화면이 만들어졌습니다.")

st.write("---") # 구분선
st.write("이곳은 앞으로 부서원들과 공유할 AI 산출물과 데이터를 시각화할 공간입니다.")

# 3. 간단한 상호작용 테스트 (버튼)
if st.button("여기를 클릭해 보세요!"):
    st.success("대시보드가 정상적으로 작동하고 있습니다! 🎉")