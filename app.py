import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta, timezone
import pickle
import os
import ast
import base64
import traceback
import streamlit.components.v1 as components

# ==========================================
# 0. 공통 설정
# ==========================================
LOGO_IMAGE = "sj_signature04.png"
DATA_FILE = "app_data.pkl"
AUTO_LOGOUT_MINUTES = 30
KST = timezone(timedelta(hours=9))

st.set_page_config(page_title="공공 개발 산출물 저장소", layout="wide", initial_sidebar_state="expanded")


def now_kst():
    return datetime.now(KST)


# ==========================================
# 1. DB 연동 (구글 시트 & 로컬 하이브리드)
# ==========================================
def load_data():
    local_data = {
        "users_db": {
            "admin": {"password": "password1234", "dept": "시스템관리자", "manager": "관리자", "approved": True}
        },
        "repository": [],
        "categories": ["전체", "교무처", "학생처", "총무처", "기획처", "단과대학", "기타"],
        "deleted_ids": []
    }

    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "rb") as f:
            loaded = pickle.load(f)
            if isinstance(loaded, dict):
                local_data.update(loaded)

    if 'deleted_ids' not in local_data:
        local_data['deleted_ids'] = []

    migrated_users = {}
    for uid, uval in local_data.get('users_db', {}).items():
        if isinstance(uval, str):
            is_admin_account = (uid == "admin")
            migrated_users[uid] = {
                "password": uval,
                "dept": "시스템관리자" if is_admin_account else "",
                "manager": "관리자" if is_admin_account else "",
                "approved": True if is_admin_account else False
            }
        elif isinstance(uval, dict):
            uval.setdefault("dept", "")
            uval.setdefault("manager", "")
            uval.setdefault("approved", uid == "admin")
            migrated_users[uid] = uval
    if "admin" not in migrated_users:
        migrated_users["admin"] = {"password": "password1234", "dept": "시스템관리자", "manager": "관리자", "approved": True}
    local_data['users_db'] = migrated_users

    # ---- 산출물 항목에 issues 필드가 없는 구버전 데이터 자동 마이그레이션 ----
    for item in local_data.get('repository', []):
        if 'issues' not in item or item['issues'] is None:
            item['issues'] = []

    local_users_before_merge = dict(local_data['users_db'])
    local_repo_before_merge = list(local_data['repository'])
    local_categories_before_merge = list(local_data.get('categories', []))

    st.session_state['db_mode'] = "Local File"
    st.session_state['gsheets_debug_log'] = []
    st.session_state['gsheets_full_traceback'] = []

    def _log(msg, level="info"):
        st.session_state['gsheets_debug_log'].append((level, msg))

    def _fmt_err(e, tag):
        full_tb = traceback.format_exc()
        st.session_state['gsheets_full_traceback'].append((tag, full_tb))
        return f"[{type(e).__name__}] {str(e) if str(e) else '(메시지 없음, 아래 전체 traceback 확인)'}"

    try:
        from streamlit_gsheets import GSheetsConnection
        _log("streamlit_gsheets 패키지 import 성공")

        if "connections" in st.secrets and "gsheets" in st.secrets["connections"]:
            _log("st.secrets에 [connections.gsheets] 설정 발견 → Google Sheets 모드로 전환 시도")
            st.session_state['db_mode'] = "Google Sheets"
            try:
                conn = st.connection("gsheets", type=GSheetsConnection)
                _log("st.connection 객체 생성 성공")
            except Exception as e_conn:
                _log(f"❌ st.connection 생성 자체가 실패했습니다: {_fmt_err(e_conn, 'connection_create')}", "error")
                conn = None

            if conn is not None:
                try:
                    users_df = conn.read(worksheet="Users", ttl=0)
                    _log(f"Users 시트 읽기 성공: {len(users_df)}행, 컬럼={list(users_df.columns)}")
                    required_cols = {'ID', 'Password'}
                    if not users_df.empty and required_cols.issubset(set(users_df.columns)):
                        users_df = users_df.dropna(subset=['ID'])
                        merged_users = {}
                        for _, row in users_df.iterrows():
                            uid = str(row['ID'])
                            pw = str(row['Password'])
                            dept = str(row['Dept']) if 'Dept' in users_df.columns and pd.notna(row.get('Dept')) else ""
                            manager = str(row['Manager']) if 'Manager' in users_df.columns and pd.notna(row.get('Manager')) else ""
                            approved_raw = row.get('Approved') if 'Approved' in users_df.columns else False
                            approved = str(approved_raw).strip().upper() in ("TRUE", "1", "예", "Y")
                            if uid == "admin":
                                approved = True
                            merged_users[uid] = {"password": pw, "dept": dept, "manager": manager, "approved": approved}
                        for uid, uinfo in local_users_before_merge.items():
                            if uid not in merged_users:
                                merged_users[uid] = uinfo
                        if "admin" not in merged_users:
                            merged_users["admin"] = {"password": "password1234", "dept": "시스템관리자", "manager": "관리자", "approved": True}
                        local_data['users_db'] = merged_users
                        _log(f"Users 병합 완료: 총 {len(merged_users)}건")
                    else:
                        _log("ℹ️ Users 시트가 비어있거나 'ID'/'Password' 헤더가 없습니다. 로컬 기본값을 사용합니다.")
                        if not users_df.empty:
                            _log(f"⚠️ 실제 컬럼명: {list(users_df.columns)} (필요: ID, Password, Dept, Manager, Approved)", "warn")
                except Exception as e_users:
                    _log(f"❌ Users 시트 읽기 실패: {_fmt_err(e_users, 'users_read')}", "error")

                try:
                    repo_df = conn.read(worksheet="Repository", ttl=0)
                    _log(f"Repository 시트 읽기 성공: {len(repo_df)}행, 컬럼={list(repo_df.columns)}")

                    if not repo_df.empty and 'id' in repo_df.columns:
                        repo_df = repo_df.dropna(subset=['id'])
                        sheet_repo = repo_df.to_dict('records')

                        final_repo = []
                        for s_item in sheet_repo:
                            s_id_str = str(s_item['id'])
                            try:
                                if pd.isna(s_item.get('feedbacks')):
                                    s_item['feedbacks'] = []
                                else:
                                    s_item['feedbacks'] = ast.literal_eval(str(s_item['feedbacks']))
                            except Exception:
                                s_item['feedbacks'] = []

                            try:
                                if pd.isna(s_item.get('issues')):
                                    s_item['issues'] = []
                                else:
                                    s_item['issues'] = ast.literal_eval(str(s_item['issues']))
                            except Exception:
                                s_item['issues'] = []

                            matching_local = next((l for l in local_repo_before_merge if str(l['id']) == s_id_str), None)
                            if matching_local and 'file_data' in matching_local:
                                s_item['file_data'] = matching_local['file_data']
                            else:
                                s_item['file_data'] = b''

                            final_repo.append(s_item)

                        local_data['repository'] = final_repo
                        _log(f"Repository 로드 완료(시트 기준): 총 {len(final_repo)}건")
                    elif not repo_df.empty and 'id' not in repo_df.columns:
                        _log(f"⚠️ Repository 시트에 'id' 헤더가 없습니다. 실제 컬럼명: {list(repo_df.columns)}", "warn")
                    else:
                        local_data['repository'] = []
                        _log("ℹ️ Repository 시트가 비어 있습니다(헤더만 있고 데이터 행 없음).")
                except Exception as e_repo:
                    _log(f"❌ Repository 시트 읽기 실패: {_fmt_err(e_repo, 'repo_read')}", "error")
                    _log("⚠️ 시트 읽기 실패로 인해 로컬 캐시 데이터를 임시로 유지합니다(비상용).", "warn")

                try:
                    cat_df = conn.read(worksheet="Categories", ttl=0)
                    _log(f"Categories 시트 읽기 성공: {len(cat_df)}행, 컬럼={list(cat_df.columns)}")
                    if not cat_df.empty and 'category' in cat_df.columns:
                        cat_list = cat_df['category'].dropna().astype(str).tolist()
                        if "전체" not in cat_list:
                            cat_list.insert(0, "전체")
                        local_data['categories'] = cat_list
                        _log(f"Categories 로드 완료(시트 기준): 총 {len(cat_list)}건")
                    elif not cat_df.empty and 'category' not in cat_df.columns:
                        _log(f"⚠️ Categories 시트에 'category' 헤더가 없습니다. 실제 컬럼명: {list(cat_df.columns)}", "warn")
                    else:
                        _log("ℹ️ Categories 시트가 비어 있습니다. 로컬 기본 분야 목록을 사용합니다.", "warn")
                except Exception as e_cat:
                    _log(f"❌ Categories 시트 읽기 실패: {_fmt_err(e_cat, 'categories_read')}", "error")
                    _log("⚠️ Categories 시트가 아직 없다면, 구글 스프레드시트에 'Categories'라는 이름의 탭을 만들고 A1 셀에 'category' 헤더를 입력해주세요.", "warn")
                    local_data['categories'] = local_categories_before_merge
        else:
            _log("st.secrets에 [connections.gsheets] 설정이 없습니다 → Local File 모드로 동작합니다.")
    except Exception as e:
        _log(f"❌ Google Sheets 연동 초기화 자체가 실패했습니다: {_fmt_err(e, 'init')}", "error")

    return local_data


def save_data(data):
    with open(DATA_FILE, "wb") as f:
        pickle.dump(data, f)

    if st.session_state.get('db_mode') == "Google Sheets":
        try:
            from streamlit_gsheets import GSheetsConnection
            conn = st.connection("gsheets", type=GSheetsConnection)

            users_rows = []
            for uid, uinfo in data['users_db'].items():
                users_rows.append({
                    "ID": uid,
                    "Password": uinfo.get("password", ""),
                    "Dept": uinfo.get("dept", ""),
                    "Manager": uinfo.get("manager", ""),
                    "Approved": bool(uinfo.get("approved", False))
                })
            users_df = pd.DataFrame(users_rows, columns=["ID", "Password", "Dept", "Manager", "Approved"])
            conn.update(worksheet="Users", data=users_df)

            if data['repository']:
                repo_df = pd.DataFrame(data['repository'])
                if 'file_data' in repo_df.columns:
                    repo_df = repo_df.drop(columns=['file_data'])
                repo_df['feedbacks'] = repo_df['feedbacks'].apply(lambda x: str(x))
                if 'issues' in repo_df.columns:
                    repo_df['issues'] = repo_df['issues'].apply(lambda x: str(x))
                conn.update(worksheet="Repository", data=repo_df)
            else:
                empty_df = pd.DataFrame(columns=['id', 'title', 'category', 'desc', 'author', 'date', 'filename', 'feedbacks', 'issues'])
                conn.update(worksheet="Repository", data=empty_df)

            cat_list = data.get('categories', [])
            cat_df = pd.DataFrame({"category": cat_list})
            conn.update(worksheet="Categories", data=cat_df)

            st.session_state['last_save_status'] = "success"
        except Exception as e:
            full_tb = traceback.format_exc()
            st.session_state.setdefault('gsheets_full_traceback', []).append(("save_data", full_tb))
            err_txt = f"[{type(e).__name__}] {str(e) if str(e) else '(메시지 없음)'}"
            st.session_state.setdefault('gsheets_debug_log', []).append(("error", f"❌ save_data 중 Google Sheets 쓰기 실패: {err_txt}"))
            st.session_state['last_save_status'] = "fail"
            st.error(f"⚠️ 구글 시트 저장에 실패했습니다! 변경사항이 시트에 반영되지 않았을 수 있습니다. 오류: {err_txt}")
    else:
        st.session_state['last_save_status'] = "local_only"


if 'app_data' not in st.session_state:
    st.session_state['app_data'] = load_data()

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if not st.session_state['logged_in'] and "user_session" in st.query_params:
    st.session_state['logged_in'] = True
    st.session_state['user_id'] = st.query_params["user_session"]
    st.session_state['last_activity'] = now_kst()

# ---- 사이드바 필터 상태 기본값 초기화 ----
if 'filter_category' not in st.session_state:
    st.session_state['filter_category'] = "전체"
if 'filter_sort' not in st.session_state:
    st.session_state['filter_sort'] = "최근 활동순"
if 'filter_keyword' not in st.session_state:
    st.session_state['filter_keyword'] = ""


def get_display_name(user_id):
    """로그인한 사용자의 '부서명 담당자명' 표기를 반환. 정보가 없으면 아이디로 대체."""
    users_db = st.session_state['app_data'].get('users_db', {})
    uinfo = users_db.get(user_id, {})
    dept = (uinfo.get('dept') or '').strip()
    manager = (uinfo.get('manager') or '').strip()
    if dept and manager:
        return f"{dept} {manager}"
    elif manager:
        return manager
    elif dept:
        return dept
    else:
        return user_id


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
# 2-1. 디자인 토큰 & 전역 스타일
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

    ::-webkit-scrollbar { width: 8px; height: 8px; }
    ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 8px; }

    .gradient-text {
        background: linear-gradient(to right, var(--accent), var(--accent-secondary));
        -webkit-background-clip: text;
        background-clip: text;
        color: transparent;
        display: inline-block;
    }

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
    .metric-card .label { font-size: 12px; color: var(--muted-foreground); font-weight: bold; }
    .metric-card .value { font-size: 28px; font-weight: 800; color: var(--foreground); }
    .metric-card .sub { font-size: 11px; color: #94a3b8; margin-top: 4px; }

    div[data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 16px !important;
        box-shadow: var(--shadow-md);
        transition: box-shadow 0.3s ease-out;
    }
    div[data-testid="stVerticalBlockBorderWrapper"]:hover {
        box-shadow: var(--shadow-lg);
    }

    div[data-testid="stVerticalBlockBorderWrapper"]:has(.login-hero-inner) {
        border-radius: 24px !important;
        box-shadow: var(--shadow-xl) !important;
        padding: 12px 24px 24px 24px !important;
        animation: fadeInUp 0.7s ease-out;
        margin-top: 24px;
    }
    .login-hero-inner { position: relative; }

    div[data-testid="stVerticalBlockBorderWrapper"]:has(.repo-card-inner) {
        border-radius: 18px !important;
        box-shadow: var(--shadow-sm) !important;
        padding: 20px 22px !important;
        margin-bottom: 18px;
        animation: fadeInUp 0.5s ease-out;
        border: 1px solid var(--border) !important;
        transition: box-shadow 0.25s ease-out, transform 0.25s ease-out;
    }
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.repo-card-inner):hover {
        box-shadow: var(--shadow-accent) !important;
        transform: translateY(-2px);
    }
    .repo-card-inner { position: relative; }

    .repo-meta-row {
        display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
        margin: 6px 0 10px 0;
    }
    .repo-cat-badge {
        font-family: var(--font-mono); font-size: 11px; color: var(--accent);
        background: rgba(0,82,255,0.08); padding: 3px 10px; border-radius: 999px;
        border: 1px solid rgba(0,82,255,0.2);
    }
    .repo-author-badge {
        font-size: 12px; color: var(--muted-foreground);
    }
    .repo-title { font-size: 19px; font-weight: 800; color: var(--foreground); margin: 0; }
    .repo-desc { font-size: 13px; color: #475569; margin: 4px 0 4px 0; }

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

    div[data-testid="stImage"] {
        background: transparent !important;
        box-shadow: none !important;
        border-radius: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
    }
    div[data-testid="stImage"] img {
        display: block;
        margin: 0 auto;
        background: transparent !important;
    }

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

    .issue-badge-open {
        display: inline-block; font-size: 11px; font-family: var(--font-mono);
        background: rgba(234,88,12,0.1); color: #C2410C; border: 1px solid rgba(234,88,12,0.3);
        padding: 2px 10px; border-radius: 999px;
    }
    .issue-badge-done {
        display: inline-block; font-size: 11px; font-family: var(--font-mono);
        background: rgba(22,163,74,0.1); color: #15803D; border: 1px solid rgba(22,163,74,0.3);
        padding: 2px 10px; border-radius: 999px;
    }

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
        with st.container(border=True):
            st.markdown("<div class='login-hero-inner'>", unsafe_allow_html=True)

            _, logo_col, _ = st.columns([1, 1.2, 1])
            with logo_col:
                st.image(LOGO_IMAGE, width=200)

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
                with st.form("login_form"):
                    user_id = st.text_input("ID 또는 이메일", key="login_id")
                    password = st.text_input("패스워드", type="password", key="login_pw")
                    st.write("<br>", unsafe_allow_html=True)
                    login_submit = st.form_submit_button("로그인", use_container_width=True)

                if login_submit:
                    users_db = st.session_state['app_data']['users_db']
                    user_info = users_db.get(user_id)
                    if user_info is None or user_info.get("password") != password:
                        st.error("아이디가 존재하지 않거나 비밀번호가 틀렸습니다.")
                    elif not user_info.get("approved", False):
                        st.warning("⏳ 아직 관리자 승인이 완료되지 않은 계정입니다. 관리자 승인 후 로그인해 주세요.")
                    else:
                        st.session_state['logged_in'] = True
                        st.session_state['user_id'] = user_id
                        st.session_state['last_activity'] = now_kst()
                        st.query_params["user_session"] = user_id
                        st.rerun()

            with tab_signup:
                with st.form("signup_form"):
                    new_dept = st.text_input("부서명", key="signup_dept")
                    new_manager = st.text_input("담당자명", key="signup_manager")
                    new_id = st.text_input("새 ID", key="signup_id")
                    new_pw = st.text_input("새 패스워드", type="password", key="signup_pw")
                    new_pw_check = st.text_input("패스워드 확인", type="password", key="signup_pw_chk")
                    signup_submit = st.form_submit_button("계정 생성하기", use_container_width=True)

                if signup_submit:
                    users_db = st.session_state['app_data']['users_db']
                    if not new_dept.strip() or not new_manager.strip() or not new_id.strip() or not new_pw.strip():
                        st.error("부서명, 담당자명, 아이디, 비밀번호는 모두 필수 입력 항목입니다.")
                    elif new_id in users_db:
                        st.error("이미 사용 중인 아이디입니다.")
                    elif new_pw != new_pw_check:
                        st.error("비밀번호가 일치하지 않습니다.")
                    else:
                        st.session_state['app_data']['users_db'][new_id] = {
                            "password": new_pw,
                            "dept": new_dept.strip(),
                            "manager": new_manager.strip(),
                            "approved": False
                        }
                        save_data(st.session_state['app_data'])
                        if st.session_state.get('last_save_status') != "fail":
                            st.success("계정 신청이 완료되었습니다. 관리자 승인 후 로그인이 가능합니다.")

            st.markdown("</div>", unsafe_allow_html=True)


# ==========================================
# 4. 사이드바 필터가 반영된 저장소 데이터 조회 함수
# ==========================================
def get_filtered_repo():
    repo_data = st.session_state['app_data']['repository']
    cat_filter = st.session_state.get('filter_category', '전체')
    keyword = st.session_state.get('filter_keyword', '').strip().lower()
    sort_option = st.session_state.get('filter_sort', '최근 활동순')

    filtered = list(repo_data)

    if cat_filter and cat_filter != "전체":
        filtered = [p for p in filtered if p.get('category', '') == cat_filter]

    if keyword:
        filtered = [
            p for p in filtered
            if keyword in p.get('title', '').lower() or keyword in p.get('desc', '').lower()
        ]

    if sort_option == "최근 활동순":
        filtered = sorted(filtered, key=lambda p: p.get('date', ''), reverse=True)
    elif sort_option == "이슈 많은순":
        filtered = sorted(filtered, key=lambda p: len(p.get('issues', [])), reverse=True)

    return filtered


# ==========================================
# 5. 메인 대시보드 화면
# ==========================================
def show_main_page():
    now = now_kst()
    if now > st.session_state['last_activity'] + timedelta(minutes=AUTO_LOGOUT_MINUTES):
        st.query_params.clear()
        st.session_state['logged_in'] = False
        st.rerun()

    col_title, col_ui = st.columns([5, 5])

    current_user_id = st.session_state.get('user_id', '')
    display_name = get_display_name(current_user_id)

    with col_title:
        st.markdown("""
            <div class='section-badge'>
                <span class='dot'></span>
                <span class='label'>Live Dashboard</span>
            </div>
        """, unsafe_allow_html=True)
        st.markdown(f"### 공공 개발 산출물 저장소(공공 GitHub) <span class='gradient-text'>프로젝트 현황</span>", unsafe_allow_html=True)
        st.caption(f"환영합니다, **{display_name}**님")

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
                st.session_state['last_activity'] = now_kst()
                st.rerun()
        with r4:
            st.markdown(f"<div style='text-align:right; font-size:12px; color:var(--muted-foreground); padding-top:10px; font-family:var(--font-mono);'>기준일자: {now_kst().strftime('%Y. %m. %d. %H:%M')}</div>", unsafe_allow_html=True)

    repo_data_all = st.session_state['app_data']['repository']
    total_projects = len(repo_data_all)
    unique_authors = len(set([p['author'] for p in repo_data_all])) if repo_data_all else 0

    all_issues = []
    for p in repo_data_all:
        all_issues.extend(p.get('issues', []))
    total_issues = len(all_issues)
    open_issues = len([i for i in all_issues if i.get('status') == '진행중'])
    done_issues = len([i for i in all_issues if i.get('status') == '완료'])

    total_feedbacks = sum(len(p.get('feedbacks', [])) for p in repo_data_all)

    is_admin = (current_user_id == 'admin')

    if is_admin:
        tab1, tab2, tab3 = st.tabs(["대시보드 현황", "산출물 커뮤니티 및 저장소", "계정 관리"])
    else:
        tab1, tab2 = st.tabs(["대시보드 현황", "산출물 커뮤니티 및 저장소"])

    # ---------------- 탭 1: 대시보드 현황 ----------------
    with tab1:
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.markdown(f"<div class='metric-card'><div class='label'>전체 프로젝트</div><div class='value'>{total_projects}</div><div class='sub'>공개(Public) 프로젝트 기준</div></div>", unsafe_allow_html=True)
        with m2:
            st.markdown(f"<div class='metric-card'><div class='label'>월간 프로젝트</div><div class='value'>{total_projects}</div><div class='sub'>최근 30일 활동</div></div>", unsafe_allow_html=True)
        with m3:
            st.markdown(f"<div class='metric-card'><div class='label'>전체 이슈</div><div class='value'>{total_issues}</div><div class='sub'>진행중 {open_issues} / 완료 {done_issues}</div></div>", unsafe_allow_html=True)
        with m4:
            st.markdown(f"<div class='metric-card'><div class='label'>프로젝트 담당자</div><div class='value'>{unique_authors}</div><div class='sub'>참여 개발자 수</div></div>", unsafe_allow_html=True)

        st.write("<br>", unsafe_allow_html=True)
        chart_col1, chart_col2 = st.columns([6, 4])
        with chart_col1:
            with st.container(border=True):
                st.markdown("##### 프로젝트 활동 현황")
                if repo_data_all:
                    dates = pd.date_range(end=now_kst().replace(tzinfo=None), periods=7).strftime("%m-%d").tolist()
                    trend_df = pd.DataFrame({
                        "일자": dates,
                        "커밋 수": [0, 0, 0, 0, 0, 0, total_projects * 2]
                    })
                    fig = px.bar(trend_df, x="일자", y="커밋 수", title="", labels={'일자': '', '커밋 수': ''})
                    fig.update_traces(marker_color='#0052FF', marker_line_width=0)
                    fig.update_layout(
                        height=260, margin=dict(l=20, r=20, t=10, b=20),
                        font=dict(family="Pretendard, sans-serif", color="#0F172A"),
                        plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)'
                    )
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("시각화할 프로젝트 데이터가 부족합니다.")
        with chart_col2:
            with st.container(border=True):
                st.markdown("##### 분야별 프로젝트 분포")
                if repo_data_all:
                    df_repo = pd.DataFrame(repo_data_all)
                    cat_counts = df_repo.get('category', pd.Series(['미분류'] * len(df_repo))).value_counts().reset_index()
                    cat_counts.columns = ['분야', '건수']
                    fig_pie = px.pie(
                        cat_counts, values='건수', names='분야', hole=0.65,
                        color_discrete_sequence=['#0052FF', '#4D7CFF', '#7fa4ff', '#a9c1ff', '#0F172A', '#64748B', '#CBD5E1']
                    )
                    fig_pie.update_layout(
                        height=260, margin=dict(l=10, r=10, t=10, b=10), showlegend=True,
                        font=dict(family="Pretendard, sans-serif", color="#0F172A"),
                        paper_bgcolor='rgba(0,0,0,0)'
                    )
                    st.plotly_chart(fig_pie, use_container_width=True)
                else:
                    st.info("등록된 프로젝트가 없어 분야 분포를 표시할 수 없습니다.")

        st.write("<br>", unsafe_allow_html=True)
        st.markdown("""
            <div class='section-badge'>
                <span class='dot'></span>
                <span class='label'>Recent Activity</span>
            </div>
        """, unsafe_allow_html=True)
        st.markdown("##### 최근 활동 프로젝트")

        if not repo_data_all:
            st.info("등록된 산출물 프로젝트가 없습니다. [산출물 커뮤니티 및 저장소] 탭에서 등록해 주세요.")
        else:
            cols = st.columns(min(len(repo_data_all), 4))
            for idx, item in enumerate(repo_data_all[-4:]):
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
        st.markdown("### 산출물 커뮤니티 및 저장소")
        st.caption("대학 구성원들이 공유한 개발 산출물을 탐색하고, 피드백과 이슈로 함께 개선해 나가는 공간입니다.")

        rm1, rm2, rm3, rm4 = st.columns(4)
        with rm1:
            st.markdown(f"<div class='metric-card'><div class='label'>전체 산출물</div><div class='value'>{total_projects}</div><div class='sub'>커뮤니티 공개 기준</div></div>", unsafe_allow_html=True)
        with rm2:
            st.markdown(f"<div class='metric-card'><div class='label'>참여 담당자</div><div class='value'>{unique_authors}</div><div class='sub'>산출물 공유자 수</div></div>", unsafe_allow_html=True)
        with rm3:
            st.markdown(f"<div class='metric-card'><div class='label'>누적 피드백</div><div class='value'>{total_feedbacks}</div><div class='sub'>커뮤니티 토론 건수</div></div>", unsafe_allow_html=True)
        with rm4:
            st.markdown(f"<div class='metric-card'><div class='label'>전체 이슈</div><div class='value'>{total_issues}</div><div class='sub'>진행중 {open_issues} / 완료 {done_issues}</div></div>", unsafe_allow_html=True)

        st.write("<br>", unsafe_allow_html=True)

        with st.expander("➕ 새로운 산출물(결과물) 업로드 하기", expanded=False):
            with st.form("upload_form", clear_on_submit=True):
                proj_name = st.text_input("프로젝트 명")
                categories_list = st.session_state['app_data'].get('categories', ['전체', '교무처', '학생처', '총무처', '기획처', '단과대학', '기타'])
                proj_cat = st.selectbox("분야 선택", options=[c for c in categories_list if c != '전체'])
                proj_desc = st.text_area("산출물 설명")
                uploaded_file = st.file_uploader(
                    "산출물 파일 첨부",
                    type=['zip', 'pdf', 'py', 'csv', 'txt', 'xlsx', 'html']
                )
                st.caption("ℹ️ 보안상 업로드된 코드/스크립트 파일을 서버에서 직접 실행하는 기능은 제공하지 않습니다. `.html` 파일은 새 창에서 미리보기가 가능합니다.")

                if st.form_submit_button("저장소에 배포하기"):
                    if proj_name and uploaded_file:
                        existing_ids = [item['id'] for item in repo_data_all] if repo_data_all else [0]
                        new_id = max(existing_ids) + 1 if existing_ids else 1
                        new_item = {
                            "id": new_id,
                            "title": proj_name,
                            "category": proj_cat,
                            "desc": proj_desc,
                            "author": st.session_state.get('user_id', '익명'),
                            "date": now_kst().strftime("%Y-%m-%d %H:%M"),
                            "filename": uploaded_file.name,
                            "file_data": uploaded_file.read(),
                            "feedbacks": [],
                            "issues": []
                        }
                        st.session_state['app_data']['repository'].append(new_item)
                        save_data(st.session_state['app_data'])
                        if st.session_state.get('last_save_status') != "fail":
                            st.success("성공적으로 공유되었습니다.")
                            st.rerun()
                    else:
                        st.error("프로젝트 명과 파일을 모두 첨부해 주세요.")

        st.markdown("---")

        filtered_repo = get_filtered_repo()
        active_filters = []
        if st.session_state.get('filter_category', '전체') != '전체':
            active_filters.append(f"분야: {st.session_state['filter_category']}")
        if st.session_state.get('filter_keyword', '').strip():
            active_filters.append(f"검색어: '{st.session_state['filter_keyword']}'")
        filter_desc = f" ({' / '.join(active_filters)} 적용 중)" if active_filters else ""

        h1, h2 = st.columns([4, 2])
        with h1:
            st.markdown(f"#### 📂 커뮤니티 저장소 목록{filter_desc}")
        with h2:
            st.markdown(f"<div style='text-align:right; padding-top:8px; color:var(--muted-foreground); font-size:13px;'>정렬: {st.session_state.get('filter_sort', '최근 활동순')} · 총 {len(filtered_repo)}건</div>", unsafe_allow_html=True)

        if not filtered_repo:
            if repo_data_all:
                st.info("사이드바 필터/검색어 조건에 맞는 산출물이 없습니다. 사이드바에서 필터를 초기화해 보세요.")
            else:
                st.info("아직 공유된 산출물이 없습니다. 위의 업로드 영역에서 첫 산출물을 공유해 보세요.")
        else:
            for item in filtered_repo:
                with st.container(border=True):
                    st.markdown("<div class='repo-card-inner'>", unsafe_allow_html=True)

                    top_col, action_col = st.columns([5, 2])
                    with top_col:
                        st.markdown(f"<p class='repo-title'>{item['title']}</p>", unsafe_allow_html=True)
                        st.markdown(f"""
                            <div class='repo-meta-row'>
                                <span class='repo-cat-badge'>{item.get('category', '일반')}</span>
                                <span class='repo-author-badge'>👤 {item['author']} · 🗓️ {item['date']}</span>
                            </div>
                        """, unsafe_allow_html=True)
                        st.markdown(f"<p class='repo-desc'>{item['desc']}</p>", unsafe_allow_html=True)

                    current_user = st.session_state.get('user_id')
                    can_manage = (current_user == item['author'] or current_user == 'admin')

                    with action_col:
                        file_ext = item['filename'].split('.')[-1].lower() if item.get('filename') else ''
                        if item.get('file_data'):
                            st.download_button(label="⬇️ 파일 다운로드", data=item['file_data'], file_name=item['filename'], mime="application/octet-stream", key=f"dl_{item['id']}", use_container_width=True)
                        else:
                            st.button("다운로드 만료됨", disabled=True, key=f"dl_{item['id']}", use_container_width=True)

                        if item.get('file_data') and file_ext == 'html':
                            b64 = base64.b64encode(item['file_data']).decode()
                            preview_html = f"""
                                <a href="data:text/html;base64,{b64}" target="_blank"
                                   style="display:block; text-align:center; padding:8px 0; margin-top:6px;
                                          background:#0F172A; color:white; border-radius:10px;
                                          font-size:14px; text-decoration:none; font-weight:500;">
                                   🖥️ 새 창에서 미리보기
                                </a>
                            """
                            st.markdown(preview_html, unsafe_allow_html=True)

                    if can_manage:
                        m_col1, m_col2, m_spacer = st.columns([1.3, 1.3, 3.4])
                        with m_col1:
                            edit_toggle_key = f"edit_toggle_{item['id']}"
                            if st.button("✏️ 내용 수정", key=f"edit_open_{item['id']}", use_container_width=True):
                                st.session_state[edit_toggle_key] = not st.session_state.get(edit_toggle_key, False)
                        with m_col2:
                            if st.button("🗑️ 산출물 삭제", key=f"del_{item['id']}", use_container_width=True):
                                st.session_state['app_data']['repository'] = [
                                    p for p in st.session_state['app_data']['repository'] if str(p['id']) != str(item['id'])
                                ]
                                save_data(st.session_state['app_data'])
                                if st.session_state.get('last_save_status') == "fail":
                                    st.stop()
                                st.success("삭제되었습니다.")
                                st.rerun()

                    if can_manage and st.session_state.get(f"edit_toggle_{item['id']}", False):
                        with st.form(f"edit_form_{item['id']}"):
                            edit_title = st.text_input("프로젝트 명 수정", value=item['title'])
                            edit_desc = st.text_area("설명 수정", value=item['desc'])
                            save_edit_btn = st.form_submit_button("수정 내용 저장")
                            if save_edit_btn:
                                item['title'] = edit_title
                                item['desc'] = edit_desc
                                save_data(st.session_state['app_data'])
                                if st.session_state.get('last_save_status') != "fail":
                                    st.session_state[f"edit_toggle_{item['id']}"] = False
                                    st.success("수정되었습니다.")
                                    st.rerun()

                    st.write("")

                    if item.get('file_data'):
                        if file_ext in ['py', 'txt', 'csv']:
                            with st.expander(f"📄 파일 미리보기 ({item['filename']})"):
                                try:
                                    st.code(item['file_data'].decode('utf-8'), language='python' if file_ext == 'py' else 'text')
                                except Exception:
                                    st.error("텍스트로 미리볼 수 없는 인코딩입니다.")
                        elif file_ext == 'html':
                            with st.expander(f"📄 파일 미리보기 ({item['filename']})"):
                                st.caption("아래는 페이지 내 임베드 미리보기입니다. 전체 화면으로 보려면 위쪽의 '새 창에서 미리보기' 버튼을 이용해 주세요.")
                                try:
                                    components.html(item['file_data'].decode('utf-8'), height=400, scrolling=True)
                                except Exception:
                                    st.error("HTML 미리보기를 렌더링할 수 없습니다.")

                    with st.expander(f"💬 피드백 및 토론 ({len(item['feedbacks'])}건)"):
                        for fb in item['feedbacks']:
                            st.markdown(f"<div style='background-color:var(--muted); padding:10px 12px; border-radius:8px; margin-bottom:6px; border-left:3px solid var(--accent);'><b style='color:var(--foreground);'>{fb['user']}</b> <span style='color:#94a3b8; font-size:11px;'>({fb['time']})</span>: {fb['text']}</div>", unsafe_allow_html=True)

                        fb_input = st.text_input("의견을 남겨주세요", key=f"fb_in_{item['id']}")
                        if st.button("피드백 등록", key=f"fb_btn_{item['id']}"):
                            if fb_input:
                                item['feedbacks'].append({"user": st.session_state.get('user_id', '익명'), "time": now_kst().strftime("%Y-%m-%d %H:%M"), "text": fb_input})
                                save_data(st.session_state['app_data'])
                                if st.session_state.get('last_save_status') != "fail":
                                    st.rerun()

                    item_issues = item.get('issues', [])
                    open_cnt = len([i for i in item_issues if i.get('status') == '진행중'])
                    done_cnt = len([i for i in item_issues if i.get('status') == '완료'])
                    with st.expander(f"🐞 이슈 ({len(item_issues)}건 · 진행중 {open_cnt} / 완료 {done_cnt})"):
                        if not item_issues:
                            st.caption("등록된 이슈가 없습니다.")
                        for iss in item_issues:
                            badge_class = "issue-badge-open" if iss.get('status') == '진행중' else "issue-badge-done"
                            ic1, ic2, ic3 = st.columns([4.5, 1.1, 1.1])
                            with ic1:
                                st.markdown(
                                    f"<span class='{badge_class}'>{iss.get('status')}</span> "
                                    f"<b>{iss.get('title')}</b> "
                                    f"<span style='color:#94a3b8; font-size:11px;'>· {iss.get('author')} · {iss.get('date')}</span>",
                                    unsafe_allow_html=True
                                )
                            with ic2:
                                if can_manage:
                                    toggle_label = "완료 처리" if iss.get('status') == '진행중' else "재오픈"
                                    if st.button(toggle_label, key=f"issue_toggle_{item['id']}_{iss['id']}", use_container_width=True):
                                        iss['status'] = '완료' if iss.get('status') == '진행중' else '진행중'
                                        save_data(st.session_state['app_data'])
                                        if st.session_state.get('last_save_status') != "fail":
                                            st.rerun()
                            with ic3:
                                if current_user == 'admin':
                                    if st.button("삭제", key=f"issue_del_{item['id']}_{iss['id']}", use_container_width=True):
                                        item['issues'] = [i for i in item_issues if i['id'] != iss['id']]
                                        save_data(st.session_state['app_data'])
                                        if st.session_state.get('last_save_status') != "fail":
                                            st.success("이슈가 삭제되었습니다.")
                                            st.rerun()

                        new_issue_title = st.text_input("새 이슈 제목", key=f"issue_in_{item['id']}")
                        if st.button("이슈 등록", key=f"issue_btn_{item['id']}"):
                            if new_issue_title.strip():
                                existing_issue_ids = [i['id'] for i in item_issues] if item_issues else [0]
                                new_issue_id = max(existing_issue_ids) + 1 if existing_issue_ids else 1
                                item_issues.append({
                                    "id": new_issue_id,
                                    "title": new_issue_title.strip(),
                                    "status": "진행중",
                                    "author": st.session_state.get('user_id', '익명'),
                                    "date": now_kst().strftime("%Y-%m-%d %H:%M")
                                })
                                item['issues'] = item_issues
                                save_data(st.session_state['app_data'])
                                if st.session_state.get('last_save_status') != "fail":
                                    st.rerun()
                            else:
                                st.warning("이슈 제목을 입력해 주세요.")

                    st.markdown("</div>", unsafe_allow_html=True)

    # ---------------- 탭 3: 계정 관리 및 분야 설정 (관리자 전용) ----------------
    if is_admin:
        with tab3:
            st.markdown("### 시스템 계정 관리")
            users_db = st.session_state['app_data']['users_db']

            users_rows = []
            for uid, uinfo in users_db.items():
                users_rows.append({
                    "사용자 ID": uid,
                    "부서명": uinfo.get("dept", ""),
                    "담당자명": uinfo.get("manager", ""),
                    "비밀번호": uinfo.get("password", ""),
                    "승인 여부": "✅ 승인됨" if uinfo.get("approved", False) else "⏳ 대기중"
                })
            users_df = pd.DataFrame(users_rows)
            st.dataframe(users_df, use_container_width=True, hide_index=True)

            st.markdown("#### 회원가입 승인 대기 목록")
            pending_users = [uid for uid, uinfo in users_db.items() if not uinfo.get("approved", False)]
            if not pending_users:
                st.info("승인 대기 중인 계정이 없습니다.")
            else:
                for uid in pending_users:
                    uinfo = users_db[uid]
                    with st.container(border=True):
                        c1, c2 = st.columns([3, 1])
                        with c1:
                            st.markdown(f"**{uid}** ({uinfo.get('dept', '-')} / {uinfo.get('manager', '-')})")
                        with c2:
                            if st.button("승인", key=f"approve_{uid}", use_container_width=True):
                                st.session_state['app_data']['users_db'][uid]["approved"] = True
                                save_data(st.session_state['app_data'])
                                if st.session_state.get('last_save_status') != "fail":
                                    st.success(f"[{uid}] 계정이 승인되었습니다.")
                                    st.rerun()

            st.markdown("#### 사용자 계정 삭제")
            target_user = st.selectbox("삭제할 사용자 선택", options=[u for u in users_db.keys() if u != 'admin'])
            if st.button("선택 계정 삭제"):
                if target_user in st.session_state['app_data']['users_db']:
                    del st.session_state['app_data']['users_db'][target_user]
                    save_data(st.session_state['app_data'])
                    if st.session_state.get('last_save_status') != "fail":
                        st.success(f"사용자 [{target_user}] 계정이 삭제되었습니다.")
                        st.rerun()

            st.markdown("---")
            st.markdown("### 사이드바 [분야] 필터 항목 구성")
            st.caption("이 항목은 구글 스프레드시트의 'Categories' 탭과 연동됩니다. 시트에서 직접 수정하셔도 되고, 아래에서 추가/삭제하시면 시트에도 자동 반영됩니다.")
            current_cats = st.session_state['app_data'].get('categories', ["전체", "교무처", "학생처", "총무처", "기획처", "단과대학", "기타"])
            st.write("현재 등록된 분야 목록:", current_cats)

            new_cat_input = st.text_input("추가할 새로운 분야명 입력")
            if st.button("분야 추가"):
                if new_cat_input and new_cat_input not in current_cats:
                    st.session_state['app_data']['categories'].append(new_cat_input)
                    save_data(st.session_state['app_data'])
                    if st.session_state.get('last_save_status') != "fail":
                        st.success(f"분야 [{new_cat_input}]가 추가되었습니다.")
                        st.rerun()

            rem_cat = st.selectbox("삭제할 분야 선택", options=[c for c in current_cats if c != '전체'])
            if st.button("선택 분야 삭제"):
                if rem_cat in st.session_state['app_data']['categories']:
                    st.session_state['app_data']['categories'].remove(rem_cat)
                    save_data(st.session_state['app_data'])
                    if st.session_state.get('last_save_status') != "fail":
                        st.success(f"분야 [{rem_cat}]가 삭제되었습니다.")
                        st.rerun()

            st.markdown("---")
            st.markdown("### ⚙️ 앱 절전(Sleep) 모드 관련 안내")
            st.info(
                "Streamlit Community Cloud(무료 플랜)는 일정 시간 접속이 없으면 앱을 자동으로 절전 상태로 전환하는 "
                "플랫폼 정책을 가지고 있습니다. 이는 앱 코드 내부에서 해결할 수 없는 부분이며, 아래와 같은 방법을 "
                "외부에서 별도로 설정해야 합니다.\n\n"
                "1. UptimeRobot, cron-job.org 같은 무료 외부 모니터링 서비스에 이 앱의 URL을 등록하고, "
                "5~10분 간격으로 자동 접속(ping)하도록 설정합니다.\n"
                "2. 지속적인 무중단 운영이 꼭 필요하다면, Streamlit의 유료 플랜이나 별도의 상시 구동 호스팅(예: 자체 서버, "
                "Render, Railway 등)으로 이전을 검토해 주세요.\n\n"
                "※ 이 안내는 Streamlit Cloud의 일반적으로 알려진 정책에 기반한 것으로, 최신 정확한 정책은 "
                "Streamlit 공식 문서에서 다시 확인해 주시기 바랍니다."
            )

            st.markdown("---")
            st.markdown("### 🔍 Google Sheets 연동 진단 로그")
            st.caption(f"현재 db_mode: **{st.session_state.get('db_mode', '알 수 없음')}**")
            debug_log = st.session_state.get('gsheets_debug_log', [])
            if debug_log:
                for level, line in debug_log:
                    if level == "error":
                        st.error(line)
                    elif level == "warn":
                        st.warning(line)
                    else:
                        st.info(line)
            else:
                st.write("진단 로그가 없습니다.")

            full_tbs = st.session_state.get('gsheets_full_traceback', [])
            if full_tbs:
                st.markdown("#### 전체 traceback (원인 정밀 확인용)")
                for tag, tb in full_tbs:
                    with st.expander(f"[{tag}] 전체 traceback 보기"):
                        st.code(tb, language="text")


# ==========================================
# 6. 사이드바 구성 (로그인 상태일 때만 노출) — 실제 필터 기능 연동
# ==========================================
def show_sidebar():
    with st.sidebar:
        col_side1, col_side2, col_side3 = st.columns([1, 2, 1])
        with col_side2:
            st.image(LOGO_IMAGE, use_container_width=True)
        st.markdown("<h3 style='text-align:center;'>AI 서정 실험실</h3>", unsafe_allow_html=True)
        st.markdown("---")

        cat_options = st.session_state['app_data'].get('categories', ["전체", "교무처", "학생처", "총무처", "기획처", "단과대학", "기타"])
        if st.session_state['filter_category'] not in cat_options:
            st.session_state['filter_category'] = "전체"

        st.selectbox("분야", options=cat_options, key="filter_category")
        st.selectbox("정렬 기준", ["최근 활동순", "이슈 많은순"], key="filter_sort")
        st.text_input("검색어", placeholder="프로젝트 검색...", key="filter_keyword")

        cb1, cb2 = st.columns(2)
        with cb1:
            if st.button("검색", use_container_width=True):
                st.rerun()
        with cb2:
            if st.button("초기화", use_container_width=True):
                st.session_state['filter_category'] = "전체"
                st.session_state['filter_sort'] = "최근 활동순"
                st.session_state['filter_keyword'] = ""
                st.rerun()

        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown("""
            <div class='sidebar-brand-card'>
                <h4 style='color: #0f172a; margin-bottom: 5px;'>AI 서정 실험실</h4>
                <p style='font-size: 13px; color: #64748b;'>대학 직원이 현장의 불편을 AI로 해결하는 실험 공간</p>
                <div class='tag'>Data & AI</div>
            </div>
        """, unsafe_allow_html=True)


# ==========================================
# 7. 최종 라우팅 (로그인 여부에 따라 사이드바 노출 제어)
# ==========================================
if not st.session_state['logged_in']:
    st.markdown("<style>[data-testid='stSidebar'] {display: none;}</style>", unsafe_allow_html=True)
    show_login_page()
else:
    show_sidebar()
    show_main_page()