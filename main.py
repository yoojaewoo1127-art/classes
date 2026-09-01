import streamlit as st
import requests

st.set_page_config(
    page_title="SSHS 겹강/수업 분반 조회기",
    page_icon="🏫",
    layout="wide"
)

# 세련된 그리드 및 카드 스타일 CSS
st.markdown("""
<style>
    .section-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 8px;
        padding-bottom: 6px;
        border-bottom: 1.5px solid #e9ecef;
    }
    .section-title {
        font-size: 1.15rem;
        font-weight: 700;
        color: #212529;
    }
    .student-badge-grid {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 6px;
        margin-top: 6px;
    }
    .student-chip {
        background-color: #f1f3f5;
        border: 1px solid #dee2e6;
        border-radius: 6px;
        padding: 5px 8px;
        font-size: 0.88rem;
        text-align: center;
        font-weight: 500;
        color: #343a40;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .student-chip b {
        color: #1c7ed6;
        margin-left: 2px;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

CLASSES_API_URL = "https://sshs.app/api/gyeopgang/classes"
STUDENTS_API_URL = "https://sshs.app/api/gyeopgang/students"

@st.cache_data(ttl=300)
def fetch_api_data():
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r_students = requests.get(STUDENTS_API_URL, headers=headers, timeout=10)
        r_classes = requests.get(CLASSES_API_URL, headers=headers, timeout=10)
        r_students.raise_for_status()
        r_classes.raise_for_status()
        return r_students.json(), r_classes.json(), None
    except Exception as e:
        return None, None, str(e)

students_raw, classes_raw, error_msg = fetch_api_data()

st.title("🏫 SSHS 수업 및 분반별 수강생 조회")

if error_msg:
    st.error(f"데이터 로드 실패: {error_msg}")
    st.stop()

# ----------------- 1. 교번/학번 -> 학생 정보 매핑 -----------------
student_info_map = {}

if isinstance(students_raw, list):
    for item in students_raw:
        if isinstance(item, dict):
            name = item.get("name", "")
            gyobun = str(item.get("gyobun", "")).strip()
            hakbun = str(item.get("hakbun", "")).strip()
            
            s_obj = {
                "name": name,
                "hakbun": hakbun,
                "display": f"{name} ({hakbun})" if hakbun else name
            }

            if gyobun:
                student_info_map[gyobun] = s_obj
            if hakbun:
                student_info_map[hakbun] = s_obj

def parse_student_entry(code):
    code_str = str(code).strip()
    if code_str in student_info_map:
        return student_info_map[code_str]
    return {"name": code_str, "hakbun": "", "display": code_str}

# ----------------- 2. 수업 데이터 파싱 -----------------
classes_list = classes_raw if isinstance(classes_raw, list) else []

def format_section_name(class_item):
    cid = class_item.get("class_id") or class_item.get("class") or class_item.get("section")
    if cid is None:
        return "1분반"
    cid_str = str(cid).strip()
    return cid_str if "반" in cid_str else f"{cid_str}분반"

def extract_students(class_item):
    for k in ["students", "members", "student_list", "roster", "takes", "list"]:
        if k in class_item and isinstance(class_item[k], list):
            return class_item[k]
    for k, v in class_item.items():
        if isinstance(v, list) and k not in ["times", "schedule", "periods", "rooms"]:
            return v
    return []

parsed_classes = []
for item in classes_list:
    if not isinstance(item, dict):
        continue
        
    subject = (
        item.get("name") or item.get("subject") or item.get("subject_name") or 
        item.get("title") or "과목명 미상"
    )
    section_name = format_section_name(item)
    raw_students = extract_students(item)
    
    parsed_students = [parse_student_entry(s) for s in raw_students]
    parsed_students.sort(key=lambda x: (x["hakbun"] == "", x["hakbun"], x["name"]))
    
    parsed_classes.append({
        "subject": str(subject).strip(),
        "section": section_name,
        "students": parsed_students,
        "count": len(parsed_students)
    })

# 과목별 데이터 그룹화
subject_summary = {}
for c in parsed_classes:
    sub = c["subject"]
    if sub not in subject_summary:
        subject_summary[sub] = {"total_students": 0, "sections": []}
    subject_summary[sub]["total_students"] += c["count"]
    subject_summary[sub]["sections"].append(c)

all_subjects = sorted(list(subject_summary.keys()))

# ----------------- 3. UI 렌더링 -----------------
if not all_subjects:
    st.warning("표시할 수업 데이터가 없습니다.")
else:
    subject_options = {
        f"{sub}  (총 {subject_summary[sub]['total_students']}명 / {len(subject_summary[sub]['sections'])}개 분반)": sub
        for sub in all_subjects
    }
    
    col_search, col_stats = st.columns([3, 1])
    with col_search:
        selected_label = st.selectbox(
            "🔍 조회할 과목을 검색하거나 선택하세요",
            options=list(subject_options.keys())
        )
        selected_subject = subject_options[selected_label]

    with col_stats:
        curr_data = subject_summary[selected_subject]
        st.metric(
            label=f"[{selected_subject}] 총 수강 인원",
            value=f"{curr_data['total_students']}명",
            delta=f"{len(curr_data['sections'])}개 분반"
        )

    st.divider()

    sections_list = curr_data["sections"]
    cols_per_row = 3
    
    for i in range(0, len(sections_list), cols_per_row):
        row_sections = sections_list[i:i + cols_per_row]
        cols = st.columns(cols_per_row)
        
        for idx, sec in enumerate(row_sections):
            with cols[idx]:
                with st.container(border=True):
                    # 분반명 & 수강 인원 헤더
                    st.markdown(f"""
                    <div class="section-header">
                        <span class="section-title">📌 {sec['section']}</span>
                        <span style="font-size: 0.85rem; color: #6c757d; font-weight: 600;">{sec['count']}명</span>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # 학생 목록 HTML 생성
                    if sec["students"]:
                        chips_list = []
                        for s in sec["students"]:
                            name_val = s["name"]
                            hakbun_val = s["hakbun"]
                            hakbun_html = f" <b>({hakbun_val})</b>" if hakbun_val else ""
                            chips_list.append(f'<div class="student-chip">{name_val}{hakbun_html}</div>')
                        
                        chips_html = "".join(chips_list)
                        st.markdown(f'<div class="student-badge-grid">{chips_html}</div>', unsafe_allow_html=True)
                    else:
                        st.caption("배정된 학생이 없습니다.")
