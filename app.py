import streamlit as st
import pandas as pd
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

# ==========================================
# 2. МОДУЛЬ ПАРСИНГА С КЭШИРОВАНИЕМ
# ==========================================
@st.cache_data(ttl=CACHE_TTL)
def fetch_student_data(year, program):
    """
    Выполняет реальный парсинг сайта БРС. 
    Кэширует результат на месяц для предотвращения повторных запросов.
    """
    data = []
    try:
        session = requests.Session()
        # В зависимости от реальных GET-параметров сайта БРС СПБГЭУ, 
        # возможно потребуется адаптировать ключи 'year' и 'program' (например, 'kurs', 'fak')
        response = session.get(BASE_URL, params={'year': year, 'program': program})
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Собираем ссылки ТОЛЬКО на существующие группы
        group_links = soup.find_all('a', class_='group-link')
        
        for link in group_links:
            group_url = link.get('href')
            group_name = link.text.strip()
            
            # Делаем абсолютную ссылку, если она относительная
            if not group_url.startswith('http'):
                group_url = f"https://rating.unecon.ru/{group_url}"

            time.sleep(REQUEST_TIMEOUT) # Таймаут между запросами групп
            
            group_resp = session.get(group_url)
            group_resp.encoding = 'utf-8'
            group_soup = BeautifulSoup(group_resp.text, 'html.parser')
            
            # Парсинг таблицы успеваемости группы
            table = group_soup.find('table')
            if not table:
                continue
                
            rows = table.find_all('tr')[1:] # Пропускаем заголовок
            for row in rows:
                cols = row.find_all(['td', 'th'])
                if len(cols) < 3: 
                    continue
                
                student_name = cols[0].text.strip()
                # Проверка на скрытое ФИО
                if not student_name or "скрыто" in student_name.lower() or "*****" in student_name:
                    student_name = "информации нет"
                
                # Здесь необходимо адаптировать индексы столбцов (cols) под структуру таблицы БРС.
                # Пример логики (нужно подставить реальные индексы столбцов семестра, предмета и балла):
                try:
                    semester = int(cols[1].text.strip())
                    subject = cols[2].text.strip()
                    score_text = cols[3].text.strip()
                    score = float(score_text) if score_text.replace('.', '', 1).isdigit() else None
                except (ValueError, IndexError):
                    continue

                data.append({
                    "Год": year,
                    "Направление": program,
                    "Группа": group_name,
                    "ФИО": student_name,
                    "Семестр": semester,
                    "Предмет": subject,
                    "Балл": score
                })
                
    except Exception as e:
        st.error(f"Ошибка при парсинге данных: {e}")
    
    return pd.DataFrame(data)

# ==========================================
# 3. ИНТЕРФЕЙС ПОЛЬЗОВАТЕЛЯ (БОКОВАЯ ПАНЕЛЬ)
# ==========================================
st.sidebar.header("Параметры анализа")

years = ["2023", "2024", "2025", "2026"]
programs = ["ПМ", "БИ", "Менеджмент", "Экономика"] 

year1 = st.sidebar.selectbox("Год поступления 1", years, index=2)
prog1 = st.sidebar.selectbox("Направление обучения 1", programs, index=0)

year2 = st.sidebar.selectbox("Год поступления 2", years, index=1)
prog2 = st.sidebar.selectbox("Направление обучения 2", programs, index=0)

with st.spinner('Загрузка и парсинг данных...'):
    df_prog1 = fetch_student_data(year1, prog1)
    df_prog2 = fetch_student_data(year2, prog2)

if df_prog1.empty and df_prog2.empty:
    st.warning("Нет данных для отображения. Проверьте правильность HTML-селекторов парсера.")
    st.stop()

# Фильтрация скрытых студентов
valid_students_prog1 = df_prog1[df_prog1['ФИО'] != "информации нет"]['ФИО'].unique() if not df_prog1.empty else []
target_student = st.sidebar.selectbox("Целевой студент (для анализа)", valid_students_prog1)

valid_all_students = pd.concat([df_prog1, df_prog2])
valid_all_students = valid_all_students[valid_all_students['ФИО'] != "информации нет"]['ФИО'].unique() if not valid_all_students.empty else []
compare_student = st.sidebar.selectbox("Студент для сравнения", valid_all_students)

# ==========================================
# 4. ДАШБОРД
# ==========================================
st.title("Дашборд аналитики успеваемости БРС")

tab1, tab2, tab3, tab4 = st.tabs([
    "Сравнение групп", 
    "Сравнение направлений", 
    "Студент vs Группа",
    "Сравнение студентов"
])

df_all = pd.concat([df_prog1, df_prog2]).drop_duplicates()

# --- Вкладка 1: Сравнение групп ---
with tab1:
    st.header("Сравнение академических групп")
    
    all_groups_list = df_all['Группа'].dropna().unique()
    if len(all_groups_list) < 2:
        st.info("Недостаточно групп для сравнения.")
    else:
        col1, col2 = st.columns(2)
        with col1:
            group_a = st.selectbox("Первая группа", all_groups_list, index=0)
        with col2:
            group_b = st.selectbox("Вторая группа", all_groups_list, index=1)
            
        data_g1 = df_all[df_all['Группа'] == group_a]
        data_g2 = df_all[df_all['Группа'] == group_b]
        
        # Поиск пересекающихся семестров
        sems1 = set(data_g1['Семестр'].dropna().unique())
        sems2 = set(data_g2['Семестр'].dropna().unique())
        intersecting_sems = sorted(list(sems1.intersection(sems2)))
        
        if not intersecting_sems:
            st.warning("У выбранных групп нет общих завершенных семестров.")
        else:
            st.write(f"**Анализ по общим семестрам:** {', '.join(map(str, intersecting_sems))}")
            
            valid_g1 = data_g1[(data_g1['Семестр'].isin(intersecting_sems)) & (data_g1['Балл'].notna())]
            valid_g2 = data_g2[(data_g2['Семестр'].isin(intersecting_sems)) & (data_g2['Балл'].notna())]
            valid_combined_groups = pd.concat([valid_g1, valid_g2])
            
            # График средних баллов по семестрам
            avg_sem_groups = valid_combined_groups.groupby(['Семестр', 'Группа'])['Балл'].mean().reset_index()
            fig_sem = px.bar(avg_sem_groups, x='Семестр', y='Балл', color='Группа', barmode='group', 
                             title="Средняя успеваемость групп по общим семестрам",
                             labels={'Балл': 'Средний балл', 'Семестр': 'Номер семестра'})
            st.plotly_chart(fig_sem, use_container_width=True)
            
            # График по смежным предметам
            subjs1 = set(valid_g1['Предмет'].unique())
            subjs2 = set(valid_g2['Предмет'].unique())
            intersecting_subjs = sorted(list(subjs1.intersection(subjs2)))
            
            if intersecting_subjs:
                subj_data = valid_combined_groups[valid_combined_groups['Предмет'].isin(intersecting_subjs)]
                avg_subj_groups = subj_data.groupby(['Предмет', 'Группа'])['Балл'].mean().reset_index()
                
                fig_subj = px.bar(avg_subj_groups, x='Предмет', y='Балл', color='Группа', barmode='group',
                                  title="Успеваемость по смежным дисциплинам",
                                  labels={'Балл': 'Средний балл'})
                st.plotly_chart(fig_subj, use_container_width=True)
            else:
                st.info("В общих семестрах нет совпадающих дисциплин.")

# --- Вкладка 2: Сравнение направлений ---
with tab2:
    st.header("Сравнение направлений")
    prog_sems1 = set(df_prog1['Семестр'].dropna().unique())
    prog_sems2 = set(df_prog2['Семестр'].dropna().unique())
    prog_intersecting = sorted(list(prog_sems1.intersection(prog_sems2)))
    
    if prog_intersecting:
        valid_prog = df_all[(df_all['Семестр'].isin(prog_intersecting)) & (df_all['Балл'].notna())]
        
        avg_prog_sem = valid_prog.groupby(['Направление', 'Семестр'])['Балл'].mean().reset_index()
        fig_prog = px.line(avg_prog_sem, x='Семестр', y='Балл', color='Направление', markers=True,
                           title="Динамика среднего балла направлений по общим семестрам")
        fig_prog.update_xaxes(type='category')
        st.plotly_chart(fig_prog, use_container_width=True)
    else:
        st.warning("Нет общих семестров для сравнения направлений.")

# --- Вкладка 3: Студент vs Группа ---
with tab3:
    st.header("Сравнение со средней успеваемостью группы")
    if target_student:
        target_data = df_prog1[(df_prog1['ФИО'] == target_student) & (df_prog1['Балл'].notna())]
        
        if not target_data.empty:
            target_group = target_data['Группа'].iloc[0]
            
            # Среднее по группе целевого студента
            group_data = df_prog1[(df_prog1['Группа'] == target_group) & (df_prog1['Балл'].notna())]
            avg_group = group_data.groupby('Семестр')['Балл'].mean().reset_index()
            avg_group['Субъект'] = f'Среднее ({target_group})'
            
            # Данные самого студента
            target_sem_avg = target_data.groupby('Семестр')['Балл'].mean().reset_index()
            target_sem_avg['Субъект'] = target_student
            
            comparison_df = pd.concat([target_sem_avg, avg_group])
            
            fig_vs_group = px.line(comparison_df, x='Семестр', y='Балл', color='Субъект', markers=True,
                                   title=f"Успеваемость: {target_student} против группы")
            fig_vs_group.update_traces(line=dict(width=3))
            fig_vs_group.update_xaxes(type='category')
            st.plotly_chart(fig_vs_group, use_container_width=True)
        else:
            st.warning("Нет данных по оценкам для данного студента.")

# --- Вкладка 4: Сравнение студентов ---
with tab4:
    st.header("Индивидуальное сравнение студентов")
    
    if target_student and compare_student:
        data_s1 = df_all[(df_all['ФИО'] == target_student) & (df_all['Балл'].notna())]
        data_s2 = df_all[(df_all['ФИО'] == compare_student) & (df_all['Балл'].notna())]
        
        col3, col4 = st.columns(2)
        with col3:
            avg1 = data_s1['Балл'].mean() if not data_s1.empty else 0
            st.metric(label=f"Средний балл: {target_student}", value=f"{avg1:.2f}")
        with col4:
            avg2 = data_s2['Балл'].mean() if not data_s2.empty else 0
            st.metric(label=f"Средний балл: {compare_student}", value=f"{avg2:.2f}")
            
        subjs_s1 = set(data_s1['Предмет'].unique())
        subjs_s2 = set(data_s2['Предмет'].unique())
        common_subjs = sorted(list(subjs_s1.intersection(subjs_s2)))
        
        if common_subjs:
            st.subheader("Сравнение по смежным предметам")
            s1_common = data_s1[data_s1['Предмет'].isin(common_subjs)].groupby('Предмет')['Балл'].mean().reset_index()
            s1_common['Студент'] = target_student
            
            s2_common = data_s2[data_s2['Предмет'].isin(common_subjs)].groupby('Предмет')['Балл'].mean().reset_index()
            s2_common['Студент'] = compare_student
            
            common_df = pd.concat([s1_common, s2_common])
            fig_students = px.bar(common_df, x='Предмет', y='Балл', color='Студент', barmode='group',
                                  title="Баллы по пересекающимся дисциплинам")
            st.plotly_chart(fig_students, use_container_width=True)
        else:
            st.info("У выбранных студентов нет общих дисциплин для детального сравнения.")
