import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# ==========================================
# 0. 공통 설정 (로고 이미지 주소)
# ==========================================
# 여기에 원하는 로고 이미지의 URL이나 깃허브에 올린 파일명(예: "logo.png")을 입력하세요.
LOGO_IMAGE = "logo-main02_1.png"

# ==========================================
# 1. 페이지 설정
# ==========================================
st.set_page_config(
    page_title="공공 GitHub 저장소",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================
# 2. 세션 상태 초기화 (임시 DB 역할)
# ==========================================
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if 'users_db' not in st.session_state:
    st.session_state['users_db'] = {'admin': 'password1234'}

if 'repository' not in st.session_state:
    st.session_state['repository'] = []

# ==========================================
# 3. 로그인 및 회원가입 화면
# ==========================================
def show_login_page():
    st.markdown("""
        <style>
        .stApp { background-color: #121216; color: white; }
        div.stButton > button {
            background-color: #5c8ae6; color: white; border: none; width: 100%; border-radius: 5px; padding: 10px;
        }
        div.stButton > button:hover { background-color: #4a75c7; color: white; }
        </style>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        st.write("<br><br><br>", unsafe_allow_html=True)
        
        # 로고 이미지 출력
        col_logo1, col_logo2, col_logo3 = st.columns([1, 2, 1])
        with col_logo2:
            st.image(LOGO_IMAGE, use_container_width=True)
            
        st.markdown("<h2 style='color: white; text-align: center; margin-top: 10px;'>공공 GitHub 저장소</h2>", unsafe_allow_html=True)
        st.write("<br>", unsafe_allow_html=True)
        
        tab_login, tab_signup = st.tabs(["로그인", "회원가입"])
        
        with tab_login:
            user_id = st.text_input("ID 또는 이메일", key="login_id")
            password = st.text_input("패스워드", type="password", key="login_pw")
            
            st.write("<br>", unsafe_allow_html=True)
            if st.button("로그인"):
                if user_id in st.session_state['users_db'] and st.session_state['users_db'][user_id] == password:
                    st.session_state['logged_in'] = True
                    st.session_state['user_id'] = user_id
                    st.rerun()
                else:
                    st.error("아이디가 존재하지 않거나 비밀번호가 틀렸습니다.")
                    
        with tab_signup:
            new_id = st.text_input("새 ID (사용할 아이디)", key="signup_id")
            new_pw = st.text_input("새 패스워드", type="password", key="signup_pw")
            new_pw_check = st.text_input("패스워드 확인", type="password", key="signup_pw_chk")
            
            st.write("<br>", unsafe_allow_html=True)
            if st.button("계정 생성하기"):
                if not new_id or not new_pw:
                    st.warning("아이디와 비밀번호를 모두 입력해주세요.")
                elif new_id in st.session_state['users_db']:
                    st.error("이미 사용 중인 아이디입니다. 다른 아이디를 입력해주세요.")
                elif new_pw != new_pw_check:
                    st.error("비밀번호가 일치하지 않습니다.")
                else:
                    st.session_state['users_db'][new_id] = new_pw
                    st.success(f"'{new_id}' 계정이 성공적으로 생성되었습니다. 로그인 탭에서 접속해주세요.")

# ==========================================
# 4. 메인 대시보드 및 커뮤니티 화면
# ==========================================
def show_main_page():
    st.markdown("""
        <style>
        .stApp { background-color: #f5f6f8; color: #333; }
        .st-emotion-cache-1wmy9hl { background-color: white; }
        .metric-card {
            background-color: white; padding: 20px; border-radius: 10px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1); text-align: left; margin-bottom: 15px;
        }
        .metric-title { font-size: 14px; color: #666; font-weight: bold; margin-bottom: 10px;}
        .metric-value { font-size: 32px; font-weight: bold; color: #111; }
        .metric-sub { font-size: 12px; color: #999; }
        </style>
    """, unsafe_allow_html=True)

    col_title, col_date = st.columns([4, 1])
    with col_title:
        st.markdown(f"### 공공 개발 산출물 저장소(공공 GitLab) 프로젝트 현황 - 환영합니다, **{st.session_state.get('user_id', '사용자')}**님!")
    with col_date:
        now = datetime.now().strftime("%Y. %m. %d. %H:%M")
        st.markdown(f"<div style='text-align: right; color: #666; margin-top: 15px;'>기준일자: {now}</div>", unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["대시보드 현황", "산출물 커뮤니티 및 저장소"])

    with tab1:
        m1, m2, m3, m4, m5 = st.columns(5)
        with m1: st.markdown("<div class='metric-card'><div class='metric-title'>전체 프로젝트</div><div class='metric-value'>29</div><div class='metric-sub'>공개(Public) 프로젝트 기준</div></div>", unsafe_allow_html=True)
        with m2: st.markdown("<div class='metric-card'><div class='metric-title'>월간 프로젝트</div><div class='metric-value'>29</div><div class='metric-sub'>최근 30일 활동</div></div>", unsafe_allow_html=True)
        with m3: st.markdown("<div class='metric-card'><div class='metric-title'>전체 이슈</div><div class='metric-value'>5</div><div class='metric-sub'>진행중 5 / 완료 0</div></div>", unsafe_allow_html=True)
        with m4: st.markdown("<div class='metric-card'><div class='metric-title'>Star</div><div class='metric-value'>21</div><div class='metric-sub'>좋아요(로그인 사용자)</div></div>", unsafe_allow_html=True)
        with m5: st.markdown("<div class='metric-card'><div class='metric-title'>프로젝트 담당자</div><div class='metric-value'>24</div><div class='metric-sub'>참여 개발자 수</div></div>", unsafe_allow_html=True)

        st.write("<br>", unsafe_allow_html=True)

        c1, c2, c3 = st.columns([2, 1, 1])
        with c1:
            st.markdown("**프로젝트 활동 현황**")
            df_activity = pd.DataFrame({
                '날짜': ['07-10', '07-11', '07-12', '07-13', '07-14', '07-15', '07-16'],
                '커밋 수': [25, 5, 8, 30, 60, 32, 2],
                '업데이트': [10, 2, 3, 12, 25, 15, 1]
            })
            fig1 = go.Figure()
            fig1.add_trace(go.Bar(x=df_activity['날짜'], y=df_activity['커밋 수'], name='커밋 수', marker_color='#3b82f6'))
            fig1.add_trace(go.Scatter(x=df_activity['날짜'], y=df_activity['업데이트'], name='업데이트된 프로젝트', mode='lines+markers', line=dict(color='#8b5cf6', width=2)))
            fig1.update_layout(height=280, margin=dict(l=0, r=0, t=10, b=0), plot_bgcolor='white', legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
            st.plotly_chart(fig1, use_container_width=True)

        with c2:
            st.markdown("**분야별 프로젝트 분포**")
            labels = ['공공행정', '재난안전', '보건복지', '국토교통', '생활폐기물']
            values = [17, 3, 3, 3, 3]
            fig2 = go.Figure(data=[go.Pie(labels=labels, values=values, hole=.5, marker_colors=['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6'])])
            fig2.update_layout(height=280, margin=dict(l=0, r=0, t=10, b=0), showlegend=False)
            st.plotly_chart(fig2, use_container_width=True)

        with c3:
            st.markdown("**활동 요약 & 언어 통계**")
            st.markdown("""
                <div style='background:white; padding:15px; border-radius:10px; font-size:14px;'>
                    <p style='display:flex; justify-content:space-between;'><span>커밋 수</span> <b>194건</b></p>
                    <p style='display:flex; justify-content:space-between;'><span>이슈 생성</span> <b>0건</b></p>
                    <p style='display:flex; justify-content:space-between;'><span>업데이트된 프로젝트 수</span> <b>20건</b></p>
                    <hr>
                    <p style='display:flex; justify-content:space-between; color:#3b82f6'><span>JavaScript</span> <b>37%</b></p>
                    <p style='display:flex; justify-content:space-between; color:#10b981'><span>Python</span> <b>25%</b></p>
                    <p style='display:flex; justify-content:space-between; color:#f59e0b'><span>HTML</span> <b>24%</b></p>
                </div>
            """, unsafe_allow_html=True)

        st.write("<br><b>최근 활동 프로젝트</b>", unsafe_allow_html=True)
        p1, p2, p3, p4, p5 = st.columns(5)
        projects = [
            ("재난문자 지도", "행정안전부 김기연", "재난안전문자 공공 API를 기반으로 최근 재난문자를 지도와 목록으로 함께 보여주는 대시보드입니다.", 23, 0),
            ("살아있는 업무지침 - 벼리", "보건복지부 박정현", "설명이 등록되지 않았습니다.", 24, 0),
            ("모두의 일기장", "종로구", "공무원들을 위한 모두의 일기장", 0, 0),
            ("나라예산 한눈에", "행정안전부 김기연", "62개 중앙관서의 세출 예산서 약 8,500건의 한글파일을 마크다운으로 변환...", 129, 1),
            ("개인정보 비식별화", "행정안전부", "내가 가진 파일 안에 개인정보를 비식별화 처리하는 프로그램.", 8, 0)
        ]
        
        for col, (title, author, desc, commit, issue) in zip([p1, p2, p3, p4, p5], projects):
            with col:
                st.markdown(f"""
                    <div style='background:white; padding:15px; border-radius:10px; height: 220px; border-top: 4px solid #3b82f6; box-shadow: 0 1px 3px rgba(0,0,0,0.1);'>
                        <div style='font-size:12px; color:#666;'>{author} <span style='float:right; color:#8b5cf6;'>활성</span></div>
                        <div style='font-size:16px; font-weight:bold; margin: 10px 0;'>{title}</div>
                        <div style='font-size:13px; color:#555; height: 80px; overflow:hidden;'>{desc}</div>
                        <div style='font-size:12px; color:#888; margin-top:10px;'>커밋 {commit} &nbsp; 이슈 {issue}</div>
                    </div>
                """, unsafe_allow_html=True)

    with tab2:
        st.markdown("### 산출물 업로드 및 피드백")
        
        with st.expander("새로운 산출물(결과물) 업로드 하기", expanded=False):
            with st.form("upload_form", clear_on_submit=True):
                proj_name = st.text_input("프로젝트 명", placeholder="예: 재난문자 자동 분류기")
                proj_desc = st.text_area("산출물 설명", placeholder="어떤 문제를 해결하는 코드/프로그램인지 설명해주세요.")
                uploaded_file = st.file_uploader("산출물 파일 첨부", type=['zip', 'pdf', 'py', 'csv', 'xlsx'])
                
                if st.form_submit_button("저장소에 배포하기"):
                    if proj_name and uploaded_file:
                        file_data = uploaded_file.read()
                        new_item = {
                            "id": len(st.session_state['repository']) + 1,
                            "title": proj_name,
                            "desc": proj_desc,
                            "author": st.session_state.get('user_id', '익명'),
                            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                            "filename": uploaded_file.name,
                            "file_data": file_data,
                            "feedbacks": []
                        }
                        st.session_state['repository'].append(new_item)
                        st.success("성공적으로 저장소에 공유되었습니다.")
                    else:
                        st.error("프로젝트 명과 파일을 모두 첨부해주세요.")

        st.markdown("---")
        st.markdown("### 커뮤니티 저장소 현황")

        if not st.session_state['repository']:
            st.info("아직 공유된 산출물이 없습니다. 첫 번째 산출물을 업로드해 보세요.")
        else:
            for item in reversed(st.session_state['repository']):
                with st.container():
                    col_info, col_action = st.columns([4, 1])
                    with col_info:
                        st.markdown(f"#### {item['title']}")
                        st.markdown(f"**공유자:** {item['author']} | **등록일:** {item['date']}")
                        st.write(item['desc'])
                    with col_action:
                        st.download_button(
                            label=f"{item['filename']} 다운로드",
                            data=item['file_data'],
                            file_name=item['filename'],
                            mime="application/octet-stream",
                            key=f"dl_{item['id']}"
                        )
                    
                    with st.expander(f"피드백 및 토론 ({len(item['feedbacks'])}건)"):
                        for fb in item['feedbacks']:
                            st.markdown(f"<div style='background-color:#f0f2f6; padding:10px; border-radius:5px; margin-bottom:5px;'>"
                                        f"<b style='color:#3b82f6;'>{fb['user']}</b> ({fb['time']}): {fb['text']}</div>", unsafe_allow_html=True)
                        
                        fb_input = st.text_input("의견을 남겨주세요", key=f"fb_in_{item['id']}")
                        if st.button("피드백 등록", key=f"fb_btn_{item['id']}"):
                            if fb_input:
                                item['feedbacks'].append({
                                    "user": st.session_state.get('user_id', '익명'),
                                    "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
                                    "text": fb_input
                                })
                                st.rerun()
                st.markdown("---")

    with st.sidebar:
        # 사이드바 상단 로고 이미지 (전역 변수 사용)
        col_side1, col_side2, col_side3 = st.columns([1, 2, 1])
        with col_side2:
            st.image(LOGO_IMAGE, use_container_width=True)
            
        st.markdown("<h3 style='text-align:center;'>AI 정부 실험실</h3>", unsafe_allow_html=True)
        st.markdown("---")
        
        st.selectbox("분야", ["전체", "행정안전부", "보건복지부", "종로구"])
        st.selectbox("정렬 기준", ["최근 활동순", "별점 높은순", "이슈 많은순"])
        st.text_input("검색어", placeholder="프로젝트 검색...")
        
        cb1, cb2 = st.columns(2)
        cb1.button("검색", use_container_width=True)
        cb2.button("초기화", use_container_width=True)

        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown("""
            <div style='background-color: #e6f0ff; padding: 20px; border-radius: 10px; text-align: center; border: 1px solid #cce0ff;'>
                <h4 style='color: #0055ff; margin-bottom: 5px;'>AI 정부 실험실</h4>
                <p style='font-size: 13px; color: #555;'>공무원이 현장의 불편을 AI로 해결하는 실험 공간</p>
                <div style='font-size: 24px; padding: 10px 0; color: #0055ff; font-weight: bold;'>Data & AI</div>
                <p style='font-size: 12px; font-weight: bold; color: #0055ff; margin-top: 10px;'>AI로 더 다정한 세상을 만들게요</p>
            </div>
        """, unsafe_allow_html=True)

        st.write("<br>", unsafe_allow_html=True)
        if st.button("로그아웃", use_container_width=True):
            st.session_state['logged_in'] = False
            st.rerun()

# ==========================================
# 5. 메인 라우팅
# ==========================================
if not st.session_state['logged_in']:
    show_login_page()
else:
    show_main_page()