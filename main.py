import streamlit as st
import requests

st.set_page_config(
    page_title="SSHS 겹강/수업 분반 조회기",
    page_icon="🏫",
    layout="wide"
)

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
# SSHS API 규격: gyobun, hakbun, name
student_map = {}

if isinstance(students_raw, list):
    for item in students_raw:
        if isinstance(item, dict):
            name = item.get("name", "")
            gyobun = str(item.get("gyobun", "")).strip()
            hakbun = str(item.get("hakbun", "")).strip()

            # 표시 형식: "홍길동 (1101)" 또는 학번이 없으면 "홍길동"
            display_str = f"{name} ({hakbun})" if hakbun else name

            # 교번, 학번 둘 다 키로 등록하여 어떤 값으로 들어와도 매핑 가능하게 처리
            if gyobun:
                student_map[gyobun] = display_str
            if hakbun:
                student_map[hakbun] = display_str

def get_student_name(student_code):
    """교번을 이름(학번)으로 변환"""
    code_str = str(student_code).strip()
    return student_map.get(code_str, code_str)

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
    
    # 교번 -> 이름(학번) 변환
    named_students = [get_student_name(s) for s in raw_students]
    
    parsed_classes.append({
        "subject": str(subject).strip(),
        "section": section_name,
        "students": named_students,
        "count": len(named_students)
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
        f"{sub} (총 {subject_summary[sub]['total_students']}명 / {len(subject_summary[sub]['sections'])}개 분반)": sub
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

    # 분반별 카드 그리드 (한 줄에 3개씩 배치)
    sections_list = curr_data["sections"]
    cols_per_row = 3
    
    for i in range(0, len(sections_list), cols_per_row):
        row_sections = sections_list[i:i + cols_per_row]
        cols = st.columns(cols_per_row)
        
        for idx, sec in enumerate(row_sections):
            with cols[idx]:
                with st.container(border=True):
                    st.subheader(f"📌 {sec['section']}")
                    st.caption(f"수강 인원: **{sec['count']}명**")
                    st.write("---")
                    
                    if sec["students"]:
                        st.markdown(" • " + " • ".join(sec["students"]))
                    else:
                        st.info("배정된 학생이 없습니다.")
