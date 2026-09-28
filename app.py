import streamlit as st
import pandas as pd
import numpy as np
import time
import requests
from bs4 import BeautifulSoup
import plotly.express as px
from datetime import timedelta

# ==========================================
# 1. КОНФИГУРАЦИЯ И НАСТРОЙКИ
# ==========================================
st.set_page_config(page_title="Аналитика БРС", layout="wide")

BASE_URL = "https://rating.unecon.ru/index.php"
CACHE_TTL = timedelta(days=30)
REQUEST_TIMEOUT = 1.5 
MOCK_DATA = True 

# ==========================================
# 2. МОДУЛЬ ПАРСИНГА С КЭШИРОВАНИЕМ
# ==========================================
@st.cache_data(ttl=CACHE_TTL)
def fetch_student_data(year, program):
    if MOCK_DATA:
        return generate_mock_data(year, program)

    data = []
    try:
        session = requests.Session()
        response = session.get(BASE_URL, params={'year': year, 'program': program})
        soup = BeautifulSoup(response.text, 'html.parser')
        
        groups = [a['href'] for a in soup.find_all('a', class_='group-link')]
        for group_url in groups:
            time.sleep(REQUEST_TIMEOUT) 
            group_resp = session.get(group_url)
            group_soup = BeautifulSoup(group_resp.text, 'html.parser')
            
            # Реальный парсинг должен будет проверять, есть ли данные в строке, 
            # и если ФИО скрыто, записывать "информации нет" и None в баллы.
            pass
                
    except Exception as e:
        st.error(f"Ошибка при парсинге: {e}")
    
    return pd.DataFrame(data)

def generate_mock_data(year, program):
    np.random.seed(hash(program + str(year)) % 10000)
    
    short_year = str(year)[-2:]
    num_groups = np.random.randint(2, 6) 
    groups = [f"{program}-{short_year}0{i}" for i in range(1, num_groups + 1)]
    
    subjects_pool = ["Математика", "Программирование", "Экономика", "Иностранный язык", "Философия", "Базы данных", "Алгоритмы"]
    subjects = np.random.choice(subjects_pool, 5, replace=False)
    
    # Корректировка семестров в зависимости от года поступления с учетом текущего 2026 года
    if year == "2025": 
        semesters = [1, 2] # 2 курс
    elif year == "2024": 
        semesters = [1, 2, 3, 4] # 3 курс
    elif year == "2023": 
        semesters = [1, 2, 3, 4, 5, 6] # 4 курс
    else: 
        semesters = [1, 2]
    
    data = []
    for group in groups:
        num_students = np.random.randint(15, 30) 
        for i in range(1, num_students + 1):
            is_hidden = np.random.rand() < 0.15 
            
            student_name = "информации нет" if is_hidden else f"Студент {i} ({group})"
            base_score = np.random.uniform(50, 95)
            
            for sem in semesters:
                for subj in subjects:
                    if is_hidden:
                        score = None 
                    else:
                        score = min(100, max(0, base_score + np.random.normal(0, 10)))
                    
                    data.append({
                        "Год": year,
                        "Направление": program,
                        "Группа": group,
                        "ФИО": student_name,
                        "Семестр": sem,
                        "Предмет": subj,
                        "Балл": round(score, 1) if score is not None else None
                    })
    return pd.DataFrame(data)

# ==========================================
# 3. ИНТЕРФЕЙС ПОЛЬЗОВАТЕЛЯ (БОКОВАЯ ПАНЕЛЬ)
# ==========================================
st.sidebar.header("Параметры анализа")

# Актуальные года обучения (без 1 курса и выпускников)
years = ["2023", "2024", "2025"]
programs = ["ПМ", "БИ", "Менеджмент", "Экономика"] 

year1 = st.sidebar.selectbox("Год поступления 1", years, index=2) # По умолчанию 2025
prog1 = st.sidebar.selectbox("Направление обучения 1", programs, index=0)

year2 = st.sidebar.selectbox("Год поступления 2 (для сравнения)", years, index=1) # По умолчанию 2024
prog2 = st.sidebar.selectbox("Направление обучения 2", programs, index=0)

df_prog1 = fetch_student_data(year1, prog1)
df_prog2 = fetch_student_data(year2, prog2)

valid_students_prog1 = df_prog1[df_prog1['ФИО'] != "информации нет"]['ФИО'].unique()
target_student = st.sidebar.selectbox("Целевой студент (Направление 1)", valid_students_prog1)

valid_all_students = pd.concat([df_prog1, df_prog2])
valid_all_students = valid_all_students[valid_all_students['ФИО'] != "информации нет"]['ФИО'].unique()
compare_student = st.sidebar.selectbox("Студент для сравнения (из любого направления)", valid_all_students, index=min(1, len(valid_all_students)-1))

# ==========================================
# 4. ДАШБОРД
# ==========================================
st.title("Дашборд аналитики успеваемости БРС")

tab1, tab2, tab3, tab4 = st.tabs([
    "Сравнение групп", 
    "Сравнение направлений", 
    "Анализ целевого студента",
    "Сравнение студентов"
])

df_all = pd.concat([df_prog1, df_prog2]).drop_duplicates()

with tab1:
    st.header("Сравнение конкретных групп")
    
    all_groups_list = df_all['Группа'].unique()
    
    col1, col2 = st.columns(2)
    with col1:
        group_a = st.selectbox("Выберите первую группу", all_groups_list, index=0)
    with col2:
        group_b = st.selectbox("Выберите вторую группу", all_groups_list, index=min(1, len(all_groups_list)-1))
        
    data_g1 = df_all[df_all['Группа'] == group_a]
    data_g2 = df_all[df_all['Группа'] == group_b]
    
    sems1 = set(data_g1['Семестр'].dropna().unique())
    sems2 = set(data_g2['Семестр'].dropna().unique())
    intersecting_sems = sorted(list(sems1.intersection(sems2)))
    
    if not intersecting_sems:
        st.warning("У выбранных групп нет пересекающихся семестров.")
    else:
        st.write(f"**Пересекающиеся семестры:** {', '.join(map(str, intersecting_sems))}")
        
        valid_g1 = data_g1[(data_g1['Семестр'].isin(intersecting_sems)) & (data_g1['Балл'].notna())]
        valid_g2 = data_g2[(data_g2['Семестр'].isin(intersecting_sems)) & (data_g2['Балл'].notna())]
        valid_combined_groups = pd.concat([valid_g1, valid_g2])
        
        avg_sem_groups = valid_combined_groups.groupby(['Семестр', 'Группа'])['Балл'].mean().reset_index()
        fig_sem_groups = px.bar(avg_sem_groups, x='Семестр', y='Балл', color='Группа', barmode='group', 
                                title="Средняя успеваемость по пересекающимся семестрам")
        st.plotly_chart(fig_sem_groups, use_container_width=True)
        
        subjs1 = set(valid_g1['Предмет'].unique())
        subjs2 = set(valid_g2['Предмет'].unique())
        intersecting_subjs = sorted(list(subjs1.intersection(subjs2)))
        
        if intersecting_subjs:
            st.write(f"**Пересекающиеся предметы:** {', '.join(intersecting_subjs)}")
            subj_data = valid_combined_groups[valid_combined_groups['Предмет'].isin(intersecting_subjs)]
            avg_subj_groups = subj_data.groupby(['Предмет', 'Группа'])['Балл'].mean().reset_index()
            
            fig_subj_groups = px.bar(avg_subj_groups, x='Предмет', y='Балл', color='Группа', barmode='group',
                                     title="Успеваемость по общим предметам (за пересекающиеся семестры)")
            st.plotly_chart(fig_subj_groups, use_container_width=True)
        else:
            st.info("У выбранных групп нет общих предметов в пересекающихся семестрах.")
            
        with st.expander("Посмотреть состав групп и скрытых студентов"):
            c1, c2 = st.columns(2)
            with c1:
                st.write(f"**{group_a}**: {len(data_g1['ФИО'].unique())} записей")
                st.dataframe(data_g1[['ФИО']].drop_duplicates().reset_index(drop=True))
            with c2:
                st.write(f"**{group_b}**: {len(data_g2['ФИО'].unique())} записей")
                st.dataframe(data_g2[['ФИО']].drop_duplicates().reset_index(drop=True))

with tab2:
    st.header("Сравнение направлений в целом")
    prog_sems1 = set(df_prog1['Семестр'].dropna().unique())
    prog_sems2 = set(df_prog2['Семестр'].dropna().unique())
    prog_intersecting = sorted(list(prog_sems1.intersection(prog_sems2)))
    
    if prog_intersecting:
        valid_prog_combined = df_all[(df_all['Семестр'].isin(prog_intersecting)) & (df_all['Балл'].notna())]
        
        avg_prog_sem = valid_prog_combined.groupby(['Направление', 'Семестр'])['Балл'].mean().reset_index()
        fig3 = px.bar(avg_prog_sem, x='Семестр', y='Балл', color='Направление', barmode='group',
                      title="Сравнение средних баллов направлений по общим семестрам")
        st.plotly_chart(fig3, use_container_width=True)
        
        prog_subjs1 = set(df_prog1['Предмет'].dropna().unique())
        prog_subjs2 = set(df_prog2['Предмет'].dropna().unique())
        prog_common_subjs = list(prog_subjs1.intersection(prog_subjs2))
        
        if prog_common_subjs:
            avg_prog_subj = valid_prog_combined[valid_prog_combined['Предмет'].isin(prog_common_subjs)].groupby(['Направление', 'Предмет'])['Балл'].mean().reset_index()
            if not avg_prog_subj.empty:
                fig4 = px.line_polar(avg_prog_subj, r='Балл', theta='Предмет', color='Направление', 
                                     line_close=True, title="Успеваемость по смежным предметам (лепестковая диаграмма)")
                fig4.update_traces(fill='toself')
                fig4.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])))
                st.plotly_chart(fig4, use_container_width=True)
    else:
        st.warning("Нет пересекающихся семестров у данных направлений.")

with tab3:
    st.header(f"Анализ целевого студента: {target_student}")
    target_data = df_prog1[(df_prog1['ФИО'] == target_student) & (df_prog1['Балл'].notna())]
    
    if not target_data.empty:
        target_group = target_data['Группа'].iloc[0]
        
        avg_prog1_overall = df_prog1[df_prog1['Балл'].notna()].groupby('Семестр')['Балл'].mean().reset_index()
        avg_prog1_overall['Субъект'] = f'Среднее по {prog1}'
        
        avg_prog2_overall = df_prog2[df_prog2['Балл'].notna()].groupby('Семестр')['Балл'].mean().reset_index()
        avg_prog2_overall['Субъект'] = f'Среднее по {prog2}'
        
        avg_group_overall = df_prog1[(df_prog1['Группа'] == target_group) & (df_prog1['Балл'].notna())].groupby('Семестр')['Балл'].mean().reset_index()
        avg_group_overall['Субъект'] = f'Среднее по группе {target_group}'
        
        target_sem_avg = target_data.groupby('Семестр')['Балл'].mean().reset_index()
        target_sem_avg['Субъект'] = target_student
        
        comparison_df = pd.concat([target_sem_avg, avg_prog1_overall, avg_prog2_overall, avg_group_overall])
        
        fig5 = px.line(comparison_df, x='Семестр', y='Балл', color='Субъект', markers=True,
                       title="Динамика студента vs Среднее")
        fig5.update_traces(line=dict(width=4), selector=dict(name=target_student))
        st.plotly_chart(fig5, use_container_width=True)
    else:
        st.warning("У студента нет данных для отображения.")

with tab4:
    st.header("Индивидуальное сравнение студентов")
    
    data_student1 = df_all[(df_all['ФИО'] == target_student) & (df_all['Балл'].notna())]
    data_student2 = df_all[(df_all['ФИО'] == compare_student) & (df_all['Балл'].notna())]
    
    col3, col4 = st.columns(2)
    with col3:
        st.subheader(target_student)
        if not data_student1.empty:
            st.dataframe(data_student1.groupby('Предмет')['Балл'].mean().reset_index().style.format({"Балл": "{:.1f}"}), hide_index=True)
    with col4:
        st.subheader(compare_student)
        if not data_student2.empty:
            st.dataframe(data_student2.groupby('Предмет')['Балл'].mean().reset_index().style.format({"Балл": "{:.1f}"}), hide_index=True)
        
    combined_students = pd.concat([data_student1, data_student2])
    if not combined_students.empty:
        fig6 = px.box(combined_students, x='ФИО', y='Балл', color='ФИО', 
                      title="Разброс баллов по всем дисциплинам")
        st.plotly_chart(fig6, use_container_width=True)
