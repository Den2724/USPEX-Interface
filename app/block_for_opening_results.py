import streamlit as st
import os

# Настройка страницы для использования всей ширины
st.set_page_config(layout="wide")

# CSS для горизонтальной прокрутки и стилизации кнопок (включая Popover)
st.markdown("""
<style>
    /* Настраиваем контейнер колонок для горизонтальной прокрутки */
    [data-testid="stHorizontalBlock"] {
        overflow-x: auto;
        flex-wrap: nowrap !important;
        gap: 2px !important; 
        padding-bottom: 15px; 
        scrollbar-width: thin; 
    }
    
    [data-testid="stHorizontalBlock"]::-webkit-scrollbar {
        height: 8px;
    }
    [data-testid="stHorizontalBlock"]::-webkit-scrollbar-track {
        background: #f1f1f1; 
        border-radius: 4px;
    }
    [data-testid="stHorizontalBlock"]::-webkit-scrollbar-thumb {
        background: #888; 
        border-radius: 4px;
    }
    
    /* Отключаем растягивание колонок */
    [data-testid="stHorizontalBlock"] > div {
        width: auto !important;
        min-width: fit-content !important;
        flex: 0 0 auto !important;
    }
    
    /* Стилизуем обычные кнопки и кнопку Popover */
    button[kind="secondary"], [data-testid="stPopover"] > button {
        white-space: nowrap !important; 
        height: 45px !important;       
        padding: 0 15px !important;    
        border-radius: 5px !important;
    }
</style>
""", unsafe_allow_html=True)

# Инициализация переменных
if "folders" not in st.session_state:
    st.session_state.folders = []
if "active_folder" not in st.session_state:
    st.session_state.active_folder = None

st.title("Результаты расчётов")

# Списки кнопок без "+" (его мы добавим отдельно как Popover)
button_names = ["Пред. результаты", "Все работы"] + st.session_state.folders

# Создаем колонки: количество папок + 1 для кнопки "+"
cols = st.columns(len(button_names) + 1)

# Отрисовываем кнопки папок
for i, btn_name in enumerate(button_names):
    with cols[i]:
        if btn_name in ["Пред. результаты", "Все работы"]:
            st.button(btn_name, key=f"btn_static_{i}")
        else:
            folder_display_name = os.path.basename(btn_name) or btn_name
            if st.button(f"📁 {folder_display_name}", key=f"btn_folder_{btn_name}"):
                st.session_state.active_folder = btn_name

# Отрисовываем кнопку "+" в последней колонке
with cols[-1]:
    # Используем Popover (всплывающее окно) вместо Tkinter
    with st.popover("➕", use_container_width=False):
        st.write("Добавление папки")
        new_folder = st.text_input("Вставьте локальный путь к папке:", placeholder="C:\\Users\\... или /Users/...")
        
        if st.button("Добавить", type="primary"):
            if not new_folder:
                st.warning("Путь не может быть пустым.")
            elif not os.path.isdir(new_folder):
                st.error("Такой папки не существует. Проверьте путь.")
            elif new_folder in st.session_state.folders:
                st.warning("Эта папка уже добавлена.")
            else:
                st.session_state.folders.append(new_folder)
                st.rerun() # Перезагружаем интерфейс для отображения новой кнопки

st.divider()

# Блок отображения содержимого выбранной папки
if st.session_state.active_folder:
    st.subheader(f"Содержимое папки:")
    st.caption(st.session_state.active_folder)
    
    try:
        files = os.listdir(st.session_state.active_folder)
        if files:
            for file in files:
                full_path = os.path.join(st.session_state.active_folder, file)
                icon = "📁" if os.path.isdir(full_path) else "📄"
                st.text(f"{icon} {file}")
        else:
            st.info("Эта папка пуста.")
    except Exception as e:
        st.error(f"Не удалось прочитать содержимое папки. Ошибка: {e}")
else:
    st.info("Выберите добавленную папку, чтобы просмотреть её содержимое.")