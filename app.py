import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import pickle
import os
import ast
import streamlit.components.v1 as components
# ==========================================
# 0. 공통 설정
# ==========================================
LOGO_IMAGE = "logo-main03_1.png"
DATA_FILE = "app_data.pkl"
AUTO_LOGOUT_MINUTES = 30
st.set_page_config(page_title="공공 개발 산출물 저장소", layout="wide", initial_sidebar_state="expanded")
# ==========================================
# 1. DB 연동 (구글 시트 & 로컬 하이브리드)
# ==========================================
def load_data():
    local_data = {
        "users_db": {"admin": "password1234"}, 
        "repository": [],
        "categories": ["전체", "교무처", "학생처", "총무처", "기획처", "단과대학", "기타"]
    }
    
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "rb") as f:
            loaded = pickle.load(f)
            if isinstance(loaded, dict):
                local_data.update(loaded)
            
    st.session_state['db_mode'] = "Local File"
    
    try:
        from streamlit_gsheets import GSheetsConnection
        if "connections" in st.secrets and "gsheets" in st.secrets["connections"]:
            st.session_state['db_mode'] = "Google Sheets"
            conn = st.connection("gsheets", type=GSheetsConnection)
            
            try:
                users_df = conn.read(worksheet="Users", usecols=[0,1], ttl=0)
                if not users_df.empty:
                    users_df = users_df.dropna(subset=['ID'])
                    local_data['users_db'] = dict(zip(users_df['ID'].astype(str), users_df['Password'].astype(str)))
            except: pass
                
            try:
                repo_df = conn.read(worksheet="Repository", ttl=0)
                if not repo_df.empty:
                    repo_df = repo_df.dropna(subset=['id'])
                    sheet_repo = repo_df.to_dict('records')
                    
                    merged_repo = []
                    for s_item in sheet_repo:
                        try:
                            if pd.isna(s_item['feedbacks']): s_item['feedbacks'] = []
                            else: s_item['feedbacks'] = ast.literal_eval(str(s_item['feedbacks']))
                        except:
                            s_item['feedbacks'] = []
                            
                        matching_local = next((l for l in local_data['repository'] if str(l['id']) == str(s_item['id'])), None)
                        if matching_local and 'file_data' in matching_local:
                            s_item['file_data'] = matching_local['file_data']
                        else:
                            s_item['file_data'] = b''
                        
                        merged_repo.append(s_item)
                    local_data['repository'] = merged_repo
            except: pass
    except Exception as e:
        pass
    return local_data
def save_data(data):
    with open(DATA_FILE, "wb") as f:
        pickle.dump(data, f)
        
    if st.session_state.get('db_mode') == "Google Sheets":
        try:
            from streamlit_gsheets import GSheetsConnection
            conn = st.connection("gsheets", type=GSheetsConnection)
            
            users_df = pd.DataFrame(list(data['users_db'].items()), columns=['ID', 'Password'])
            conn.update(worksheet="Users", data=users_df)
            
            if data['repository']:
                repo_df = pd.DataFrame(data['repository'])
                if 'file_data' in repo_df.columns:
                    repo_df = repo_df.drop(columns=['file_data'])
                repo_df['feedbacks'] = repo_df['feedbacks'].apply(lambda x: str(x))
                conn.update(worksheet="Repository", data=repo_df)
        except Exception as e:
            pass
if 'app_data' not in st.session_state:
    st.session_state['app_data'] = load_data()
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if not st.session_state['logged_in'] and "user_session" in st.query_params:
    st.session_state['logged_in'] = True
    st.session_state['user_id'] = st.query_params["user_session"]
    st.session_state['last_activity'] = datetime.now()
# ==========================================
# 2. 커스텀 CSS & 자바스크립트 타이머
# ==========================================
def inject_timer_js():
    expiry_time = st.session_state['last_activity'] + timedelta(minutes=AUTO_LOGOUT_MINUTES)
    expiry_timestamp = expiry_time.timestamp() * 1000
    components.html(f"""
        <script>
        const expiry = {expiry_timestamp};
        setInterval(function() {{
            const now = new Date().getTime();
            const distance = expiry - now;
            const elem = window.parent.document.getElementById('realtime-timer');
            if (distance < 0) {{
                if(elem) elem.innerHTML = "00:00";
            }} else {{
                const m = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
                const s = Math.floor((distance % (1000 * 60)) / 1000);
                if(elem) elem.innerHTML = (m < 10 ? "0" + m : m) + ":" + (s < 10 ? "0" + s : s);
            }}
        }}, 1000);
        </script>
    """, height=0)

# ==========================================
# 2-1. 디자인 토큰 & 전역 스타일 (Minimalist Modern 디자인 시스템 - 한글 최적화)
# ==========================================
def inject_design_system():
    st.markdown("""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.css');
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&display=swap');

    :root {
        --background: #FAFAFA;
        --foreground: #0F172A;
        --muted: #F1F5F9;
        --muted-foreground: #64748B;
        --accent: #0052FF;
        --accent-secondary: #4D7CFF;
        --accent-foreground: #FFFFFF;
        --border: #E2E8F0;
        --card: #FFFFFF;
        --ring: #0052FF;

        --font-display: 'Pretendard', -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
        --font-body: 'Pretendard', -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
        --font-mono: 'JetBrains Mono', 'Pretendard', monospace;

        --shadow-sm: 0 1px 3px rgba(0,0,0,0.06);
        --shadow-md: 0 4px 6px rgba(0,0,0,0.07);
        --shadow-lg: 0 10px 15px rgba(0,0,0,0.08);
        --shadow-xl: 0 20px 25px rgba(0,0,0,0.1);
        --shadow-accent: 0 4px 14px rgba(0,82,255,0.25);
        --shadow-accent-lg: 0 8px 24px rgba(0,82,255,0.35);
    }

    /* ---------- 전역 배경 & 타이포 (한국어 최적화: Pretendard) ---------- */
    html, body, .stApp, [class*="css"] {
        font-family: var(--font-body) !important;
    }
    .stApp {
        background-color: var(--background);
        color: var(--foreground);
    }
    h1, h2, h3 {
        font-family: var(--font-display) !important;
        font-weight: 800;
        letter-spacing: -0.02em;
        color: var(--foreground);
    }
    h4, h5, h6 {
        font-family: var(--font-display) !important;
        font-weight: 700;
        letter-spacing: -0.01em;
    }
    code, .mono-label {
        font-family: var(--font-mono) !important;
    }

    /* ---------- 스크롤바 살짝 다듬기 ---------- */
    ::-webkit-scrollbar { width: 8px; height: 8px; }
    ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 8px; }

    /* ---------- 그라디언트 텍스트 ---------- */
    .gradient-text {
        background: linear-gradient(to right, var(--accent), var(--accent-secondary));
        -webkit-background-clip: text;
        background-clip: text;
        color: transparent;
        display: inline-block;
    }

    /* ---------- 섹션 라벨(배지) ---------- */
    .section-badge {
        display: inline-flex;
        align-items: center;
        gap: 10px;
        border-radius: 999px;
        border: 1px solid rgba(0,82,255,0.3);
        background: rgba(0,82,255,0.05);
        padding: 6px 18px;
        margin-bottom: 10px;
    }
    .section-badge .dot {
        width: 8px; height: 8px; border-radius: 50%;
        background: var(--accent);
        animation: pulse-dot 2s infinite;
        flex-shrink: 0;
    }
    .section-badge .label {
        font-family: var(--font-mono);
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 0.15em;
        color: var(--accent);
        white-space: nowrap;
    }
    @keyframes pulse-dot {
        0%, 100% { transform: scale(1); opacity: 1; }
        50% { transform: scale(1.3); opacity: 0.7; }
    }

    /* ---------- 카드 (metric / panel) ---------- */
    .metric-card {
        background-color: var(--card);
        padding: 20px;
        border-radius: 16px;
        border: 1px solid var(--border);
        margin-bottom: 15px;
        box-shadow: var(--shadow-md);
        transition: box-shadow 0.3s ease-out, transform 0.3s ease-out;
    }
    .metric-card:hover {
        box-shadow: var(--shadow-lg);
        transform: translateY(-3px);
    }
    .panel-card {
        background-color: var(--card);
        padding: 24px;
        border-radius: 16px;
        border: 1px solid var(--border);
        margin-bottom: 15px;
        height: 100%;
        box-shadow: var(--shadow-md);
        transition: box-shadow 0.3s ease-out;
    }
    .panel-card:hover { box-shadow: var(--shadow-lg); }

    /* ---------- 프로젝트 카드 ---------- */
    .project-card {
        background-color: var(--card);
        padding: 16px;
        border-radius: 14px;
        border: 1px solid var(--border);
        height: 190px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        box-shadow: var(--shadow-sm);
        transition: box-shadow 0.25s ease-out, transform 0.25s ease-out;
        animation: fadeInUp 0.6s ease-out;
    }
    .project-card:hover {
        box-shadow: var(--shadow-accent);
        transform: translateY(-2px);
    }
    @keyframes fadeInUp {
        from { opacity: 0; transform: translateY(16px); }
        to { opacity: 1; transform: translateY(0); }
    }

    /* ---------- 인버전(다크) 섹션 ---------- */
    .invert-section {
        background-color: var(--foreground);
        color: #F8FAFC;
        border-radius: 20px;
        padding: 26px;
        position: relative;
        overflow: hidden;
        box-shadow: var(--shadow-xl);
        background-image: radial-gradient(circle, rgba(255,255,255,0.05) 1px, transparent 1px);
        background-size: 22px 22px;
    }
    .invert-section::before {
        content: "";
        position: absolute;
        top: -60px; right: -60px;
        width: 200px; height: 200px;
        background: var(--accent);
        opacity: 0.18;
        filter: blur(80px);
        border-radius: 50%;
        pointer-events: none;
    }
    .invert-section h4, .invert-section h5, .invert-section h6, .invert-section p, .invert-section div {
        color: #F8FAFC !important;
    }
    .invert-accent-value {
        background: linear-gradient(to right, #7fa4ff, #c7d7ff);
        -webkit-background-clip: text;
        background-clip: text;
        color: transparent !important;
        font-weight: 700;
    }

    /* ---------- 로그인 히어로 카드 ---------- */
    .login-hero {
        background: var(--card);
        border: 1px solid var(--border);
        border-radius: 24px;
        padding: 44px 36px 36px 36px;
        box-shadow: var(--shadow-xl);
        position: relative;
        overflow: hidden;
        animation: fadeInUp 0.7s ease-out;
    }
    /* 은은한 배경 글로우만 유지 (불필요한 사각형 요소 제거) */
    .login-hero .bg-glow {
        position: absolute;
        bottom: -90px; left: -90px;
        width: 220px; height: 220px;
        background: radial-gradient(circle, rgba(0,82,255,0.10), transparent 70%);
        border-radius: 50%;
        pointer-events: none;
        z-index: 0;
    }
    .login-hero .bg-glow-top {
        position: absolute;
        top: -70px; right: -70px;
        width: 180px; height: 180px;
        background: radial-gradient(circle, rgba(77,124,255,0.10), transparent 70%);
        border-radius: 50%;
        pointer-events: none;
        z-index: 0;
    }
    .login-hero > * { position: relative; z-index: 1; }

    /* ---------- 타이머 배지 ---------- */
    #realtime-timer-badge {
        background: linear-gradient(135deg, var(--foreground), #1e293b);
        color: white;
        text-align: center;
        padding: 8px 0;
        font-family: var(--font-mono);
        font-weight: 600;
        font-size: 13px;
        border-radius: 8px;
        box-shadow: var(--shadow-sm);
        letter-spacing: 0.05em;
    }

    /* ---------- 사이드바 브랜드 카드 ---------- */
    .sidebar-brand-card {
        background: linear-gradient(160deg, #F1F5F9, #FFFFFF);
        padding: 22px;
        border-radius: 16px;
        text-align: center;
        border: 1px solid var(--border);
        box-shadow: var(--shadow-sm);
    }
    .sidebar-brand-card .tag {
        font-family: var(--font-mono);
        font-size: 20px;
        font-weight: 700;
        padding: 8px 0;
        background: linear-gradient(to right, var(--accent), var(--accent-secondary));
        -webkit-background-clip: text;
        background-clip: text;
        color: transparent;
    }

    /* ---------- Streamlit 기본 위젯 커스터마이즈 (가능한 범위 내) ---------- */
    div[data-testid="stButton"] > button {
        border-radius: 10px !important;
        font-weight: 500 !important;
        transition: all 0.2s ease-out !important;
    }
    div[data-testid="stButton"] > button:hover {
        transform: translateY(-1px);
        color: var(--accent) !important;
    }
    div[data-testid="stButton"] > button:active {
        transform: scale(0.98);
    }
    div[data-testid="stFormSubmitButton"] > button {
        background: linear-gradient(to right, var(--accent), var(--accent-secondary)) !important;
        color: white !important;
        border: none !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
        box-shadow: var(--shadow-sm);
        transition: all 0.2s ease-out !important;
    }
    div[data-testid="stFormSubmitButton"] > button:hover {
        filter: brightness(1.08);
        box-shadow: var(--shadow-accent-lg);
        transform: translateY(-1px);
    }
    div[data-testid="stFormSubmitButton"] > button:active {
        transform: scale(0.98);
    }
    div[data-baseweb="tab-list"] { gap: 6px; }
    button[data-baseweb="tab"] {
        border-radius: 8px 8px 0 0 !important;
        font-weight: 500;
    }
    div[data-testid="stTextInput"] input, div[data-testid="stTextArea"] textarea {
        border-radius: 10px !important;
        border: 1px solid var(--border) !important;
    }
    div[data-testid="stTextInput"] input:focus, div[data-testid="stTextArea"] textarea:focus {
        border-color: var(--accent) !important;
        box-shadow: 0 0 0 2px rgba(0,82,255,0.25) !important;
    }
    hr { border-color: var(--border) !important; }
    </style>
    """, unsafe_allow_html=True)

inject_design_system()

# ==========================================
# 3. 로그인 및 회원가입 화면
# ==========================================
def show_login_page():
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        st.write("<br><br>", unsafe_allow_html=True)
        st.markdown("""
            <div class='login-hero'>
                <div class='bg-glow'></div>
                <div class='bg-glow-top'></div>
        """, unsafe_allow_html=True)

        col_logo1, col_logo2, col_logo3 = st.columns([1, 2, 1])
        with col_logo2: st.image(LOGO_IMAGE, use_container_width=True)

        st.markdown("""
            <div style='text-align:center; margin-top:10px;'>
                <div class='section-badge' style='margin-bottom:14px;'>
                    <span class='dot'></span>
                    <span class='label'>Public Dev Repository</span>
                </div>
            </div>
            <h2 style='text-align: center; margin-top: 4px;'>
                공공 개발 산출물 <span class='gradient-text'>저장소</span>
            </h2>
            <p style='text-align:center; color:var(--muted-foreground); font-size:14px; margin-top:-6px;'>
                대학 구성원의 개발 산출물을 안전하게 공유하고 관리하세요
            </p>
        """, unsafe_allow_html=True)
        st.write("<br>", unsafe_allow_html=True)
        
        tab_login, tab_signup = st.tabs(["로그인", "회원가입"])
        
        with tab_login:
            user_id = st.text_input("ID 또는 이메일", key="login_id")
            password = st.text_input("패스워드", type="password", key="login_pw")
            st.write("<br>", unsafe_allow_html=True)
            if st.button("로그인", use_container_width=True):
                users_db = st.session_state['app_data']['users_db']
                if user_id in users_db and users_db[user_id] == password:
                    st.session_state['logged_in'] = True
                    st.session_state['user_id'] = user_id
                    st.session_state['last_activity'] = datetime.now()
                    st.query_params["user_session"] = user_id
                    st.rerun()
                else: st.error("아이디가 존재하지 않거나 비밀번호가 틀렸습니다.")
                    
        with tab_signup:
            new_id = st.text_input("새 ID", key="signup_id")
            new_pw = st.text_input("새 패스워드", type="password", key="signup_pw")
            new_pw_check = st.text_input("패스워드 확인", type="password", key="signup_pw_chk")
            if st.button("계정 생성하기", use_container_width=True):
                users_db = st.session_state['app_data']['users_db']
                if new_id in users_db: st.error("이미 사용 중인 아이디입니다.")
                elif new_pw != new_pw_check: st.error("비밀번호가 불일치합니다.")
                else:
                    st.session_state['app_data']['users_db'][new_id] = new_pw
                    save_data(st.session_state['app_data'])
                    st.success("계정 생성 완료. 로그인해 주세요.")

        st.markdown("</div>", unsafe_allow_html=True)
# ==========================================
# 4. 메인 대시보드 화면
# ==========================================
def show_main_page():
    now = datetime.now()
    if now > st.session_state['last_activity'] + timedelta(minutes=AUTO_LOGOUT_MINUTES):
        st.query_params.clear()
        st.session_state['logged_in'] = False
        st.rerun()
    col_title, col_ui = st.columns([5, 5])
    
    with col_title:
        st.markdown("""
            <div class='section-badge'>
                <span class='dot'></span>
                <span class='label'>Live Dashboard</span>
            </div>
        """, unsafe_allow_html=True)
        st.markdown(f"### 공공 개발 산출물 저장소(공공 GitHub) <span class='gradient-text'>프로젝트 현황</span>", unsafe_allow_html=True)
        st.caption(f"환영합니다, **{st.session_state.get('user_id', '사용자')}**님")
    
    with col_ui:
        r1, r2, r3, r4 = st.columns([1, 1, 1, 1.5])
        with r1:
            if st.button("로그아웃", use_container_width=True):
                st.query_params.clear()
                st.session_state['logged_in'] = False
                st.rerun()
        with r2:
            st.markdown(f"<div id='realtime-timer-badge'><span id='realtime-timer'>--:--</span></div>", unsafe_allow_html=True)
            inject_timer_js()
        with r3:
            if st.button("연장", use_container_width=True):
                st.session_state['last_activity'] = datetime.now()
                st.rerun()
        with r4:
            st.markdown(f"<div style='text-align:right; font-size:12px; color:var(--muted-foreground); padding-top:10px; font-family:var(--font-mono);'>기준일자: {datetime.now().strftime('%Y. %m. %d. %H:%M')}</div>", unsafe_allow_html=True)
    repo_data = st.session_state['app_data']['repository']
    total_projects = len(repo_data)
    unique_authors = len(set([p['author'] for p in repo_data]))
    is_admin = (st.session_state.get('user_id') == 'admin')
    if is_admin:
        tab1, tab2, tab3 = st.tabs(["대시보드 현황", "산출물 커뮤니티 및 저장소", "계정 관리"])
    else:
        tab1, tab2 = st.tabs(["대시보드 현황", "산출물 커뮤니티 및 저장소"])
    # ---------------- 탭 1: 대시보드 현황 ----------------
    with tab1:
        # 1. 상단 지표 카드 5개 (빈 네모칸 제거됨)
        m1, m2, m3, m4, m5 = st.columns(5)
        with m1: st.markdown(f"<div class='metric-card'><div style='font-size: 12px; color: var(--muted-foreground); font-weight: bold;'>전체 프로젝트</div><div style='font-size: 28px; font-weight: 800; color: var(--foreground);'>{total_projects}</div><div style='font-size: 11px; color: #94a3b8; margin-top: 4px;'>공개(Public) 프로젝트 기준</div></div>", unsafe_allow_html=True)
        with m2: st.markdown(f"<div class='metric-card'><div style='font-size: 12px; color: var(--muted-foreground); font-weight: bold;'>월간 프로젝트</div><div style='font-size: 28px; font-weight: 800; color: var(--foreground);'>{total_projects}</div><div style='font-size: 11px; color: #94a3b8; margin-top: 4px;'>최근 30일 활동</div></div>", unsafe_allow_html=True)
        with m3: st.markdown("<div class='metric-card'><div style='font-size: 12px; color: var(--muted-foreground); font-weight: bold;'>전체 이슈</div><div style='font-size: 28px; font-weight: 800; color: var(--foreground);'>0</div><div style='font-size: 11px; color: #94a3b8; margin-top: 4px;'>진행중 0 / 완료 0</div></div>", unsafe_allow_html=True)
        with m4: st.markdown("<div class='metric-card'><div style='font-size: 12px; color: var(--muted-foreground); font-weight: bold;'>Star</div><div style='font-size: 28px; font-weight: 800;' class='gradient-text'>0</div><div style='font-size: 11px; color: #94a3b8; margin-top: 4px;'>좋아요(로그인 사용자)</div></div>", unsafe_allow_html=True)
        with m5: st.markdown(f"<div class='metric-card'><div style='font-size: 12px; color: var(--muted-foreground); font-weight: bold;'>프로젝트 담당자</div><div style='font-size: 28px; font-weight: 800; color: var(--foreground);'>{unique_authors}</div><div style='font-size: 11px; color: #94a3b8; margin-top: 4px;'>참여 개발자 수</div></div>", unsafe_allow_html=True)
        st.write("<br>", unsafe_allow_html=True)
        # 2. 중단 3분할 영역 (실제 데이터 반영)
        chart_col1, chart_col2, chart_col3 = st.columns([5, 3, 2])
        with chart_col1:
            st.markdown("<div class='panel-card'>", unsafe_allow_html=True)
            st.markdown("##### 프로젝트 활동 현황")
            if repo_data:
                dates = pd.date_range(end=datetime.today(), periods=7).strftime("%m-%d").tolist()
                trend_df = pd.DataFrame({
                    "일자": dates,
                    "커밋 수": [0, 0, 0, 0, 0, 0, total_projects * 2]
                })
                fig = px.bar(trend_df, x="일자", y="커밋 수", title="", labels={'일자': '', '커밋 수': ''})
                fig.update_traces(marker_color='#0052FF', marker_line_width=0)
                fig.update_layout(
                    height=240, margin=dict(l=20, r=20, t=10, b=20),
                    font=dict(family="Pretendard, sans-serif", color="#0F172A"),
                    plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)'
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("시각화할 프로젝트 데이터가 부족합니다.")
            st.markdown("</div>", unsafe_allow_html=True)
        with chart_col2:
            st.markdown("<div class='panel-card'>", unsafe_allow_html=True)
            st.markdown("##### 분야별 프로젝트 분포")
            if repo_data:
                df_repo = pd.DataFrame(repo_data)
                cat_counts = df_repo.get('category', pd.Series(['미분류']*len(df_repo))).value_counts().reset_index()
                cat_counts.columns = ['분야', '건수']
                fig_pie = px.pie(
                    cat_counts, values='건수', names='분야', hole=0.65,
                    color_discrete_sequence=['#0052FF', '#4D7CFF', '#7fa4ff', '#a9c1ff', '#0F172A', '#64748B', '#CBD5E1']
                )
                fig_pie.update_layout(
                    height=240, margin=dict(l=10, r=10, t=10, b=10), showlegend=True,
                    font=dict(family="Pretendard, sans-serif", color="#0F172A"),
                    paper_bgcolor='rgba(0,0,0,0)'
                )
                st.plotly_chart(fig_pie, use_container_width=True)
            else:
                st.info("등록된 프로젝트가 없어 분야 분포를 표시할 수 없습니다.")
            st.markdown("</div>", unsafe_allow_html=True)
        with chart_col3:
            st.markdown(f"""
                <div class='invert-section'>
                    <div style='position:relative; z-index:1;'>
                        <h5 style='margin-top:0;'>활동 요약 <span style='font-size:11px; color:#94a3b8; font-weight:400;'>(최근 7일)</span></h5>
                        <hr style='border-color:rgba(255,255,255,0.15) !important; margin:10px 0;'>
                        <p style='font-size:13px; margin:6px 0;'>커밋 수: <span class='invert-accent-value'>{total_projects * 2}건</span></p>
                        <p style='font-size:13px; margin:6px 0;'>이슈 생성: <span class='invert-accent-value'>0건</span></p>
                        <p style='font-size:13px; margin:6px 0;'>업데이트된 프로젝트: <span class='invert-accent-value'>{total_projects}건</span></p>
                        <hr style='border-color:rgba(255,255,255,0.15) !important; margin:10px 0;'>
                        <h6 style='margin-bottom:4px;'>언어 사용 통계</h6>
                        <p style='font-size:12px; color:#cbd5e1;'>Python / HTML 중심 운영</p>
                    </div>
                </div>
            """, unsafe_allow_html=True)
        st.write("<br>", unsafe_allow_html=True)
        st.markdown("""
            <div class='section-badge'>
                <span class='dot'></span>
                <span class='label'>Recent Activity</span>
            </div>
        """, unsafe_allow_html=True)
        st.markdown("##### 최근 활동 프로젝트")
        
        # 3. 하단 최근 활동 프로젝트 카드 그리드
        if not repo_data:
            st.info("등록된 산출물 프로젝트가 없습니다. [산출물 커뮤니티 및 저장소] 탭에서 등록해 주세요.")
        else:
            cols = st.columns(min(len(repo_data), 4))
            for idx, item in enumerate(repo_data[-4:]):
                with cols[idx % len(cols)]:
                    cat_val = item.get('category', '일반')
                    st.markdown(f"""
                        <div class="project-card">
                            <div>
                                <span style="font-family:var(--font-mono); font-size: 10px; color: var(--accent); background:rgba(0,82,255,0.08); padding:2px 8px; border-radius:6px;">{cat_val}</span>
                                <span style="font-size: 11px; color: #94a3b8;"> · {item['author']}</span>
                                <h6 style="margin: 8px 0 4px 0; color: var(--foreground); font-weight: 700;">{item['title']}</h6>
                                <p style="font-size: 12px; color: #475569; overflow: hidden; text-overflow: ellipsis; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;">{item['desc']}</p>
                            </div>
                            <div style="font-size: 11px; color: #94a3b8; border-top: 1px solid #f1f5f9; padding-top: 8px;">
                                등록일: {item['date']}
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
    # ---------------- 탭 2: 산출물 커뮤니티 및 저장소 ----------------
    with tab2:
        st.markdown("""
            <div class='section-badge'>
                <span class='dot'></span>
                <span class='label'>Community Repository</span>
            </div>
        """, unsafe_allow_html=True)
        st.markdown("### 산출물 업로드 및 피드백")
        with st.expander("새로운 산출물(결과물) 업로드 하기", expanded=False):
            with st.form("upload_form", clear_on_submit=True):
                proj_name = st.text_input("프로젝트 명")
                categories_list = st.session_state['app_data'].get('categories', ['전체', '교무처', '학생처', '총무처', '기획처', '단과대학', '기타'])
                proj_cat = st.selectbox("분야 선택", options=[c for c in categories_list if c != '전체'])
                proj_desc = st.text_area("산출물 설명")
                uploaded_file = st.file_uploader("산출물 파일 첨부", type=['zip', 'pdf', 'py', 'csv', 'txt', 'xlsx'])
                
                if st.form_submit_button("저장소에 배포하기"):
                    if proj_name and uploaded_file:
                        new_item = {
                            "id": len(repo_data) + 1,
                            "title": proj_name,
                            "category": proj_cat,
                            "desc": proj_desc,
                            "author": st.session_state.get('user_id', '익명'),
                            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                            "filename": uploaded_file.name,
                            "file_data": uploaded_file.read(),
                            "feedbacks": []
                        }
                        st.session_state['app_data']['repository'].append(new_item)
                        save_data(st.session_state['app_data'])
                        st.success("성공적으로 공유되었습니다.")
                        st.rerun()
                    else: st.error("프로젝트 명과 파일을 모두 첨부해 주세요.")
        st.markdown("---")
        st.markdown("### 커뮤니티 저장소 현황")
        if not repo_data:
            st.info("아직 공유된 산출물이 없습니다.")
        else:
            for item in reversed(repo_data):
                with st.container():
                    col_info, col_action = st.columns([4, 1])
                    with col_info:
                        c_tag = item.get('category', '일반')
                        st.markdown(f"#### {item['title']} <span style='font-family:var(--font-mono); font-size:11px; background:rgba(0,82,255,0.08); color:var(--accent); padding:3px 10px; border-radius:999px; border:1px solid rgba(0,82,255,0.2);'>{c_tag}</span>", unsafe_allow_html=True)
                        st.markdown(f"**공유자:** {item['author']} | **등록일:** {item['date']}")
                        st.write(item['desc'])
                    with col_action:
                        if item.get('file_data'):
                            st.download_button(label="파일 다운로드", data=item['file_data'], file_name=item['filename'], mime="application/octet-stream", key=f"dl_{item['id']}")
                        else:
                            st.button("다운로드 만료됨", disabled=True, key=f"dl_{item['id']}")
                    
                    current_user = st.session_state.get('user_id')
                    if current_user == item['author'] or current_user == 'admin':
                        with st.expander("산출물 관리 (수정/삭제)"):
                            with st.form(f"edit_form_{item['id']}"):
                                edit_title = st.text_input("프로젝트 명 수정", value=item['title'])
                                edit_desc = st.text_area("설명 수정", value=item['desc'])
                                c_col1, c_col2 = st.columns(2)
                                update_btn = c_col1.form_submit_button("내용 수정")
                                delete_btn = c_col2.form_submit_button("산출물 삭제")
                                
                                if update_btn:
                                    item['title'] = edit_title
                                    item['desc'] = edit_desc
                                    save_data(st.session_state['app_data'])
                                    st.success("수정되었습니다.")
                                    st.rerun()
                                if delete_btn:
                                    st.session_state['app_data']['repository'] = [p for p in repo_data if p['id'] != item['id']]
                                    save_data(st.session_state['app_data'])
                                    st.success("삭제되었습니다.")
                                    st.rerun()
                    if item.get('file_data'):
                        file_ext = item['filename'].split('.')[-1].lower()
                        if file_ext in ['py', 'txt', 'csv']:
                            with st.expander(f"파일 미리보기 ({item['filename']})"):
                                try: st.code(item['file_data'].decode('utf-8'), language='python' if file_ext == 'py' else 'text')
                                except: st.error("텍스트로 미리볼 수 없는 인코딩입니다.")
                    with st.expander(f"피드백 및 토론 ({len(item['feedbacks'])}건)"):
                        for fb in item['feedbacks']:
                            st.markdown(f"<div style='background-color:var(--muted); padding:10px 12px; border-radius:8px; margin-bottom:6px; border-left:3px solid var(--accent);'><b style='color:var(--foreground);'>{fb['user']}</b> <span style='color:#94a3b8; font-size:11px;'>({fb['time']})</span>: {fb['text']}</div>", unsafe_allow_html=True)
                        
                        fb_input = st.text_input("의견을 남겨주세요", key=f"fb_in_{item['id']}")
                        if st.button("피드백 등록", key=f"fb_btn_{item['id']}"):
                            if fb_input:
                                item['feedbacks'].append({"user": st.session_state.get('user_id', '익명'), "time": datetime.now().strftime("%Y-%m-%d %H:%M"), "text": fb_input})
                                save_data(st.session_state['app_data'])
                                st.rerun()
                st.markdown("---")
    # ---------------- 탭 3: 계정 관리 및 분야 설정 (관리자 전용) ----------------
    if is_admin:
        with tab3:
            st.markdown("### 시스템 계정 관리")
            users_db = st.session_state['app_data']['users_db']
            users_df = pd.DataFrame(list(users_db.items()), columns=['사용자 ID', '비밀번호'])
            st.dataframe(users_df, use_container_width=True, hide_index=True)
            
            st.markdown("#### 사용자 계정 삭제")
            target_user = st.selectbox("삭제할 사용자 선택", options=[u for u in users_db.keys() if u != 'admin'])
            if st.button("선택 계정 삭제"):
                if target_user in st.session_state['app_data']['users_db']:
                    del st.session_state['app_data']['users_db'][target_user]
                    save_data(st.session_state['app_data'])
                    st.success(f"사용자 [{target_user}] 계정이 삭제되었습니다.")
                    st.rerun()
            st.markdown("---")
            st.markdown("### 사이드바 [분야] 필터 항목 구성")
            current_cats = st.session_state['app_data'].get('categories', ["전체", "교무처", "학생처", "총무처", "기획처", "단과대학", "기타"])
            st.write("현재 등록된 분야 목록:", current_cats)
            
            new_cat_input = st.text_input("추가할 새로운 분야명 입력")
            if st.button("분야 추가"):
                if new_cat_input and new_cat_input not in current_cats:
                    st.session_state['app_data']['categories'].append(new_cat_input)
                    save_data(st.session_state['app_data'])
                    st.success(f"분야 [{new_cat_input}]가 추가되었습니다.")
                    st.rerun()
                    
            rem_cat = st.selectbox("삭제할 분야 선택", options=[c for c in current_cats if c != '전체'])
            if st.button("선택 분야 삭제"):
                if rem_cat in st.session_state['app_data']['categories']:
                    st.session_state['app_data']['categories'].remove(rem_cat)
                    save_data(st.session_state['app_data'])
                    st.success(f"분야 [{rem_cat}]가 삭제되었습니다.")
                    st.rerun()

# ==========================================
# 5. 사이드바 구성 (로그인 상태일 때만 노출)
# ==========================================
def show_sidebar():
    with st.sidebar:
        col_side1, col_side2, col_side3 = st.columns([1, 2, 1])
        with col_side2: st.image(LOGO_IMAGE, use_container_width=True)
        st.markdown("<h3 style='text-align:center;'>AI 서정 실험실</h3>", unsafe_allow_html=True)
        st.markdown("---")
        
        cat_options = st.session_state['app_data'].get('categories', ["전체", "교무처", "학생처", "총무처", "기획처", "단과대학", "기타"])
        st.selectbox("분야", options=cat_options)
        st.selectbox("정렬 기준", ["최근 활동순", "별점 높은순", "이슈 많은순"])
        st.text_input("검색어", placeholder="프로젝트 검색...")
        cb1, cb2 = st.columns(2)
        cb1.button("검색", use_container_width=True)
        cb2.button("초기화", use_container_width=True)
        
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown("""
            <div class='sidebar-brand-card'>
                <h4 style='color: #0f172a; margin-bottom: 5px;'>AI 서정 실험실</h4>
                <p style='font-size: 13px; color: #64748b;'>대학 직원이 현장의 불편을 AI로 해결하는 실험 공간</p>
                <div class='tag'>Data & AI</div>
            </div>
        """, unsafe_allow_html=True)

# ==========================================
# 6. 최종 라우팅 (로그인 여부에 따라 사이드바 노출 제어)
# ==========================================
if not st.session_state['logged_in']:
    st.markdown("<style>[data-testid='stSidebar'] {display: none;}</style>", unsafe_allow_html=True)
    show_login_page()
else:
    show_sidebar()
    show_main_page()