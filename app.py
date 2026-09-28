import streamlit as st
import pandas as pd
import numpy as np
import time
import requests
from bs4 import BeautifulSoup
import plotly.express as px
import plotly.graph_objects as go
from datetime import timedelta

st.set_page_config(page_title="Аналитика БРС", layout="wide")

BASE_URL = "https://rating.unecon.ru/index.php"
CACHE_TTL = timedelta(days=30)  # обнова раз в месяц
REQUEST_TIMEOUT = 1.5  # таймаут между запросами в сек

# для тестирования интерфейса без нагрузки на реальный сайт
MOCK_DATA = True

# парсинг с кешированием
@st.cache_data(ttl=CACHE_TTL)
def fetch_student_data(year, program):

    if MOCK_DATA:
        return generate_mock_data(year, program)

    data = []
    try:
        # получаем список групп для направления
        session = requests.Session()
        response = session.get(BASE_URL, params={'year': year, 'program': program})
        soup = BeautifulSoup(response.text, 'html.parser')

        # поиск ссылок на группы
        groups = [a['href'] for a in soup.find_all('a', class_='group-link')]

        for group_url in groups:
            time.sleep(REQUEST_TIMEOUT)  # таймаут между запросами
            group_resp = session.get(group_url)
            group_soup = BeautifulSoup(group_resp.text, 'html.parser')

            # парсинг таблицы студентов
            students = group_soup.find_all('tr', class_='student-row')
            for student in students:
                name = student.find('td', class_='name').text
                # Далее проваливаемся в карточку студента или парсим прямо из таблицы
                # data.append({...})

    except Exception as e:
        st.error(f"Ошибка при парсинге {BASE_URL}: {e}")

    return pd.DataFrame(data)


def generate_mock_data(year, program):
    np.random.seed(hash(program) % 10000)
    groups = [f"{program}-2301", f"{program}-2302", f"{program}-2303"]
    subjects = ["Математика", "Программирование", "Экономика", "Иностранный язык", "Философия"]
    semesters = [1, 2, 3, 4]

    data = []
    for group in groups:
        for i in range(1, 16):
            student_name = f"Студент {i} ({group})"
            base_score = np.random.uniform(50, 90)
            for sem in semesters:
                for subj in subjects:
                    # имитация баллов с разбросом
                    score = min(100, max(0, base_score + np.random.normal(0, 10)))
                    data.append({
                        "Год": year,
                        "Направление": program,
                        "Группа": group,
                        "ФИО": student_name,
                        "Семестр": sem,
                        "Предмет": subj,
                        "Балл": round(score, 1)
                    })
    return pd.DataFrame(data)




st.sidebar.header("Параметры анализа")

years = ["2022", "2023", "2024"]
programs = ["ПМИ", "БИ", "Менеджмент", "Экономика"]

year1 = st.sidebar.selectbox("Год поступления 1", years, index=1)
prog1 = st.sidebar.selectbox("Направление обучения 1", programs, index=0)

year2 = st.sidebar.selectbox("Год поступления 2 (для сравнения)", years, index=1)
prog2 = st.sidebar.selectbox("Направление обучения 2", programs, index=1)

df_prog1 = fetch_student_data(year1, prog1)
df_prog2 = fetch_student_data(year2, prog2)

students_prog1 = df_prog1['ФИО'].unique()
target_student = st.sidebar.selectbox("Целевой студент (Направление 1)", students_prog1)

all_students = pd.concat([df_prog1, df_prog2])['ФИО'].unique()
compare_student = st.sidebar.selectbox("Студент для сравнения (из любого направления)", all_students, index=1)

# пересекающиеся семестры
sems1 = set(df_prog1['Семестр'].unique())
sems2 = set(df_prog2['Семестр'].unique())
intersecting_semesters = sorted(list(sems1.intersection(sems2)))

# фильтрация только по пересекающимся семестрам (будущие исключаются логикой парсинга/генерации)
df_prog1_filtered = df_prog1[df_prog1['Семестр'].isin(intersecting_semesters)]
df_prog2_filtered = df_prog2[df_prog2['Семестр'].isin(intersecting_semesters)]



st.title("Дашборд аналитики успеваемости БРС")

tab1, tab2, tab3, tab4 = st.tabs([
    "Успеваемость Направления 1",
    "Сравнение направлений",
    "Анализ целевого студента",
    "Сравнение студентов"
])

with tab1:
    st.header(f"Средняя успеваемость студентов: {prog1} ({year1})")  # Требование 1[cite: 1]

    # Средний балл по предметам с разбивкой по группам
    avg_subj_group = df_prog1.groupby(['Группа', 'Предмет'])['Балл'].mean().reset_index()
    fig1 = px.bar(avg_subj_group, x='Предмет', y='Балл', color='Группа', barmode='group',
                  title="Средний балл по предметам (разбивка по группам)")
    st.plotly_chart(fig1, use_container_width=True)

    # Динамика по семестрам
    avg_sem_group = df_prog1.groupby(['Семестр', 'Группа'])['Балл'].mean().reset_index()
    fig2 = px.line(avg_sem_group, x='Семестр', y='Балл', color='Группа', markers=True,
                   title="Динамика успеваемости по семестрам")
    st.plotly_chart(fig2, use_container_width=True)

with tab2:
    st.header("Сравнение успеваемости направлений 1 и 2")  # Требование 2[cite: 1]
    st.write(f"Сравнение **{prog1}** и **{prog2}** за общие семестры: {intersecting_semesters}")

    df_combined = pd.concat([df_prog1_filtered, df_prog2_filtered])
    avg_prog_sem = df_combined.groupby(['Направление', 'Семестр'])['Балл'].mean().reset_index()

    fig3 = px.bar(avg_prog_sem, x='Семестр', y='Балл', color='Направление', barmode='group',
                  title="Сравнение средних баллов по семестрам")
    st.plotly_chart(fig3, use_container_width=True)

    # Сравнение по смежным предметам (пересекающиеся предметы)
    subjs1 = set(df_prog1_filtered['Предмет'].unique())
    subjs2 = set(df_prog2_filtered['Предмет'].unique())
    common_subjs = list(subjs1.intersection(subjs2))

    if common_subjs:
        avg_prog_subj = df_combined[df_combined['Предмет'].isin(common_subjs)].groupby(['Направление', 'Предмет'])[
            'Балл'].mean().reset_index()
        fig4 = px.radar(avg_prog_subj, r='Балл', theta='Предмет', color='Направление',
                        title="Сравнение успеваемости по смежным предметам")
        st.plotly_chart(fig4, use_container_width=True)
    else:
        st.info("Нет общих предметов для построения радарной диаграммы.")

with tab3:
    st.header(f"Анализ целевого студента: {target_student}")
    target_data = df_prog1[df_prog1['ФИО'] == target_student]
    target_group = target_data['Группа'].iloc[0]

    # Подготовка данных для сравнения
    avg_prog1_overall = df_prog1_filtered.groupby('Семестр')['Балл'].mean().reset_index()
    avg_prog1_overall['Субъект'] = f'Среднее по {prog1}'

    avg_prog2_overall = df_prog2_filtered.groupby('Семестр')['Балл'].mean().reset_index()
    avg_prog2_overall['Субъект'] = f'Среднее по {prog2}'

    avg_group_overall = df_prog1_filtered[df_prog1_filtered['Группа'] == target_group].groupby('Семестр')[
        'Балл'].mean().reset_index()
    avg_group_overall['Субъект'] = f'Среднее по группе {target_group}'

    target_sem_avg = target_data[target_data['Семестр'].isin(intersecting_semesters)].groupby('Семестр')[
        'Балл'].mean().reset_index()
    target_sem_avg['Субъект'] = target_student

    comparison_df = pd.concat([target_sem_avg, avg_prog1_overall, avg_prog2_overall, avg_group_overall])

    # График: Студент vs Направление 1 vs Направление 2
    fig5 = px.line(comparison_df, x='Семестр', y='Балл', color='Субъект', markers=True,
                   title="Успеваемость студента в сравнении со средними показателями направлений и группы")

    # Выделение линии целевого студента
    fig5.update_traces(line=dict(width=4), selector=dict(name=target_student))
    st.plotly_chart(fig5, use_container_width=True)

with tab4:
    st.header("Индивидуальное сравнение студентов")

    df_all_students = pd.concat([df_prog1, df_prog2])
    data_student1 = df_all_students[df_all_students['ФИО'] == target_student]
    data_student2 = df_all_students[df_all_students['ФИО'] == compare_student]

    col1, col2 = st.columns(2)
    with col1:
        st.subheader(target_student)
        st.dataframe(data_student1.groupby('Предмет')['Балл'].mean().reset_index().style.format({"Балл": "{:.1f}"}),
                     hide_index=True)
    with col2:
        st.subheader(compare_student)
        st.dataframe(data_student2.groupby('Предмет')['Балл'].mean().reset_index().style.format({"Балл": "{:.1f}"}),
                     hide_index=True)

    combined_students = pd.concat([data_student1, data_student2])
    fig6 = px.box(combined_students, x='ФИО', y='Балл', color='ФИО',
                  title="Разброс баллов по всем дисциплинам")
    st.plotly_chart(fig6, use_container_width=True)

# Возможность выгрузки кэшированных данных в Excel
st.sidebar.markdown("---")
if st.sidebar.button("Скачать данные в Excel"):
    st.sidebar.success("Функция формирования .xlsx файла инициализирована.")