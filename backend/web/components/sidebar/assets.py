

import streamlit as st


def render_sidebar_assets():
    st.markdown(
        """
    <script>
    // 保存到localStorage
    function saveToLocalStorage(key, value) {
        localStorage.setItem('trading_agents_' + key, value);
        console.log('Saved to localStorage:', key, value);
    }

    // 从localStorage读取
    function loadFromLocalStorage(key, defaultValue) {
        const value = localStorage.getItem('trading_agents_' + key);
        console.log('Loaded from localStorage:', key, value || defaultValue);
        return value || defaultValue;
    }

    // 页面加载时恢复设置
    window.addEventListener('load', function() {
        console.log('Page loaded, restoring settings...');
    });
    </script>
    """,
        unsafe_allow_html=True,
    )
    st.markdown(
        """
    <style>
    /* 侧边栏宽度和基础样式已在global_sidebar.css中定义 */

    /* 侧边栏特定的内边距和组件样式 */
    section[data-testid="stSidebar"] .block-container,
    section[data-testid="stSidebar"] > div > div,
    .css-1d391kg,
    .css-1lcbmhc,
    .css-1cypcdb {
        padding-top: 0.2rem !important;
        padding-left: 0.5rem !important;
        padding-right: 0.5rem !important;
        padding-bottom: 0.75rem !important;
    }

    /* 优化selectbox容器 */
    section[data-testid="stSidebar"] .stSelectbox {
        margin-bottom: 0.4rem !important;
        width: 100% !important;
    }

    /* 优化下拉框选项文本 */
    section[data-testid="stSidebar"] .stSelectbox label {
        font-size: 0.85rem !important;
        font-weight: 600 !important;
        margin-bottom: 0.2rem !important;
    }

    /* 优化文本输入框 */
    section[data-testid="stSidebar"] .stTextInput > div > div > input {
        font-size: 0.8rem !important;
        padding: 0.3rem 0.5rem !important;
        width: 100% !important;
    }

    /* 优化按钮样式 */
    section[data-testid="stSidebar"] .stButton > button {
        width: 100% !important;
        font-size: 0.8rem !important;
        padding: 0.3rem 0.5rem !important;
        margin: 0.1rem 0 !important;
        border-radius: 0.3rem !important;
    }

    /* 优化标题样式 */
    section[data-testid="stSidebar"] h3 {
        font-size: 1rem !important;
        margin-bottom: 0.5rem !important;
        margin-top: 0rem !important;
        padding: 0 !important;
    }

    /* 优化info框样式 */
    section[data-testid="stSidebar"] .stAlert {
        padding: 0.4rem !important;
        margin: 0.3rem 0 !important;
        font-size: 0.75rem !important;
    }

    /* 优化markdown文本 */
    section[data-testid="stSidebar"] .stMarkdown {
        margin-bottom: 0.3rem !important;
        padding: 0 !important;
    }

    /* 优化分隔线 */
    section[data-testid="stSidebar"] hr {
        margin: 0.75rem 0 !important;
    }

    /* 确保下拉框选项完全可见 - 调整为适合320px */
    .stSelectbox [data-baseweb="select"] {
        min-width: 260px !important;
        max-width: 280px !important;
    }

    /* 优化下拉框选项列表 */
    .stSelectbox [role="listbox"] {
        min-width: 260px !important;
        max-width: 290px !important;
    }

    /* 额外的边距控制 - 确保左右边距减小 */
    .sidebar .element-container {
        padding: 0 !important;
        margin: 0.2rem 0 !important;
    }

    /* 强制覆盖默认样式 */
    .css-1d391kg .element-container {
        padding-left: 0.5rem !important;
        padding-right: 0.5rem !important;
    }

    /* 减少侧边栏顶部空白 */
    section[data-testid="stSidebar"] > div:first-child {
        padding-top: 0 !important;
        margin-top: 0 !important;
    }

    /* 减少第一个元素的顶部边距 */
    section[data-testid="stSidebar"] .element-container:first-child {
        margin-top: 0 !important;
        padding-top: 0 !important;
    }

    /* 减少标题的顶部边距 */
    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3 {
        margin-top: 0 !important;
        padding-top: 0 !important;
    }
    </style>
    """,
        unsafe_allow_html=True,
    )
