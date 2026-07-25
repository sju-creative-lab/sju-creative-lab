import streamlit as st

# 1. 웹페이지 기본 설정
st.set_page_config(page_title="AI 서정 실험실", page_icon="🚀", layout="wide")

# 2. 사이드바 (메뉴 역할)
with st.sidebar:
    st.header("📂 메뉴")
    st.info("현재 개발 중인 AI 프로젝트 목록입니다.")
    st.radio("이동할 프로젝트를 선택하세요:", ["메인 홈", "프로젝트 A: 문서 요약 AI", "프로젝트 B: 자동 번역 봇"])

# 3. 메인 화면 타이틀
st.title("🚀 AI 서정 실험실 통합 대시보드")
st.markdown("개발된 AI 산출물을 확인하고, 다운로드 및 피드백을 남길 수 있는 공간입니다.")
st.divider() # 구분선

# 4. 프로젝트 현황 및 결과물 공유 영역
st.subheader("📌 [프로젝트 A] 업무용 문서 자동 요약 AI")
st.caption("진행 상태: 🟢 개발 완료 | 담당자: AI 서정 실험실")

# 레이아웃을 2개의 단(컬럼)으로 나누기
col1, col2 = st.columns(2)

with col1:
    st.markdown("#### 📝 프로젝트 개요")
    st.write("회의록이나 긴 보고서 텍스트를 입력하면, 핵심 내용 3줄로 자동 요약해 주는 AI 모델입니다.")
    st.write("**주요 기능:**")
    st.write("- 한국어 완벽 지원")
    st.write("- PDF, Word 파일 텍스트 추출 가능")
    
    # 5. 다운로드 버튼 기능
    st.markdown("#### 💾 결과물 다운로드")
    # 테스트용 가짜 데이터 다운로드 (실제 파일로 교체 가능)
    sample_code = "print('이것은 다운로드된 AI 산출물 코드입니다.')"
    st.download_button(
        label="📥 AI 요약 프로그램 다운로드 (.py)",
        data=sample_code,
        file_name="ai_summary_tool.py",
        mime="text/plain"
    )

with col2:
    st.markdown("#### 📊 현재 개발 현황")
    st.write("버전 1.0 완성도")
    st.progress(100) # 100% 진행률 바
    st.write("버전 2.0 (다국어 지원) 개발 진행률")
    st.progress(35)  # 35% 진행률 바

st.divider()

# 6. 커뮤니티 / 피드백 영역
st.subheader("💬 결과물 피드백 및 의견 남기기")
st.write("사용해 보시고 개선할 점이나 추가되었으면 하는 기능을 자유롭게 남겨주세요!")

# 피드백 입력 폼
with st.form("feedback_form"):
    user_name = st.text_input("작성자 이름 (또는 부서명)")
    feedback_text = st.text_area("피드백 내용을 입력하세요")
    submitted = st.form_submit_button("피드백 제출하기")

    if submitted:
        if user_name and feedback_text:
            st.success(f"{user_name}님의 소중한 의견이 등록되었습니다! 감사합니다. 👍")
        else:
            st.warning("이름과 내용을 모두 입력해 주세요.")

            st.divider()
st.subheader("📤 내 결과물 업로드하기 (부서원용)")
st.write("개발한 코드(.py)나 산출물(.pdf, .zip 등)을 여기에 끌어다 놓으세요.")

# 파일 업로드 기능 창 만들기
uploaded_file = st.file_uploader("파일 선택", accept_multiple_files=False)

if uploaded_file is not None:
    st.success(f"'{uploaded_file.name}' 파일이 성공적으로 업로드 준비가 되었습니다! 🎉")
    # 실제로는 여기서 데이터베이스나 클라우드로 파일을 전송하는 코드가 들어갑니다.