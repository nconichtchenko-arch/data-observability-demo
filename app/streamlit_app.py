import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import create_engine

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "dwh_marketplace",
    "user": "dwh_user",
    "password": "dwh_password",
}

@st.cache_data
def load_data():
    engine = create_engine(
        f"postgresql+psycopg2://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['dbname']}"
    )
    query = "SELECT * FROM public.airflow_logs_metrics"
    df = pd.read_sql(query, engine)
    return df

def main():
    st.set_page_config(page_title="Data Observability", layout="wide")
    st.title("📡 Data Observability: Мониторинг пайплайнов Airflow")
    st.markdown("Анализ логов Airflow: статусы задач, ошибки, длительность.")

    df = load_data()

    # Метрики
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Всего задач", len(df))
    col2.metric("Успешных", len(df[df['status'] == 'success']))
    col3.metric("Проваленных", len(df[df['status'] == 'failed']))
    col4.metric("Уникальных DAG'ов", df['dag_id'].nunique())

    st.markdown("---")

    # График 1: Статусы по DAG'ам
    st.subheader("📊 Статусы задач по DAG'ам")
    status_counts = df.groupby(['dag_id', 'status']).size().reset_index(name='count')
    fig1 = px.bar(status_counts, x='dag_id', y='count', color='status', barmode='group',
                  title="Success vs Failed по DAG'ам")
    st.plotly_chart(fig1, use_container_width=True)

    # График 2: Топ ошибок
    st.subheader("🚨 Топ ошибок")
    errors = df[df['status'] == 'failed']['error_message'].dropna().value_counts().head(10).reset_index()
    errors.columns = ['error_message', 'count']
    if not errors.empty:
        fig2 = px.bar(errors, x='count', y='error_message', orientation='h',
                      title="Самые частые ошибки")
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("Ошибок не найдено.")

    # Таблица
    st.subheader("📋 Детальные данные")
    st.dataframe(df.sort_values('id', ascending=False), use_container_width=True)

if __name__ == "__main__":
    main()
