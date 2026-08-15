import os
import psycopg2
from datetime import datetime
import streamlit as st
from dotenv import load_dotenv
from groq import Groq

# 1. إعدادات الصفحة والتصميم
st.set_page_config(
    page_title="AI Requirement Elicitor", 
    page_icon="🤖", 
    layout="wide"
)

# إضافة تنسيقات CSS مخصصة لتجميل الواجهة والدعم الكامل للغة العربية
st.markdown("""
    <style>
    .main {
        direction: rtl;
        text-align: right;
    }
    .stChatMessage {
        border-radius: 10px;
        padding: 10px;
        margin-bottom: 10px;
    }
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        font-weight: bold;
    }
    div[data-testid="stSidebarHeader"] {
        padding-top: 1rem;
    }
    </style>
""", unsafe_allow_html=True)

# 2. تحميل المفاتيح والبيئة
load_dotenv()
api_key = os.getenv("GROQ_API_KEY")
db_url = os.getenv("DATABASE_URL")

# الهيدر الرئيسي للموقع
col_title, col_status = st.columns([3, 1])
with col_title:
    st.title("🤖 مساعد استنباط المتطلبات الذكي")
    st.caption("نظام التفاعل الذكي لاستخراج وثيقة المتطلبات (SRS Document)")

if not api_key:
    st.error("❌ لم يتم العثور على GROQ_API_KEY في الإعدادات.")
    st.stop()

client = Groq(api_key=api_key)

# 3. إعداد قاعدة البيانات السحابية (Supabase PostgreSQL)
def get_db_connection():
    return psycopg2.connect(db_url)

def init_db():
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS chat_logs 
                     (id SERIAL PRIMARY KEY, 
                      role TEXT, 
                      content TEXT, 
                      timestamp TIMESTAMP)''')
        conn.commit()
        c.close()
        conn.close()
    except Exception as e:
        st.error(f"خطأ في الاتصال بقاعدة البيانات السحابية: {e}")

def save_to_db(role, content):
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("INSERT INTO chat_logs (role, content, timestamp) VALUES (%s, %s, %s)",
                  (role, content, datetime.now()))
        conn.commit()
        c.close()
        conn.close()
    except Exception as e:
        print(f"خطأ في حفظ البيانات: {e}")

# 4. توجيه النظام (System Prompt)
SYSTEM_PROMPT = """أنت مهندس هندسة متطلبات برمجيات محترف (Requirements Engineer).
دورك إجراء مقابلة تفاعلية مع العميل لاستنباط المتطلبات.
القواعد:
1. اطرح سؤالاً واحداً محدداً في كل مرة.
2. اسأل أسئلة عميقة لكشف الغموض في الفكرة.
3. ركز على استخراج المتطلبات الوظيفية (FR) وغير الوظيفية (NFR)."""

# 5. الشريط الجانبي المحسّن
with st.sidebar:
    st.image("https://img.icons8.com/isometric-folders/100/bot.png", width=80)
    st.title("لوحة التحكم")
    st.markdown("---")
    
    st.subheader("🌐 حالة النظام")
    st.success("🟢 متصل بـ Supabase")
    st.caption("التخزين السحابي نشط ولحظي.")
    
    st.markdown("---")
    st.subheader("⚙️ الخيارات")
    if st.button("🗑️ مسح الجلسة وبدء جديد", type="secondary"):
        st.session_state.messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "assistant", "content": "مرحباً بك! أنا مساعدك الذكي. أخبرني عن فكرة مشروعك لنبدأ باستنباط المتطلبات معاً."}
        ]
        st.rerun()

    st.markdown("---")
    st.caption("AI Requirements Elicitor v1.0")

# 6. تهيئة الذاكرة المؤقتة
if "messages" not in st.session_state:
    init_db()
    st.session_state.messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "assistant", "content": "مرحباً بك! أنا مساعدك الذكي. أخبرني عن فكرة مشروعك لنبدأ باستنباط المتطلبات معاً."}
    ]

# 7. عرض المحادثة في حاوية مخصصة
chat_container = st.container()

with chat_container:
    for msg in st.session_state.messages:
        if msg["role"] != "system":
            avatar = "🤖" if msg["role"] == "assistant" else "👤"
            with st.chat_message(msg["role"], avatar=avatar):
                st.write(msg["content"])

# 8. معالجة مدخلات المستخدم واستجابة AI
if prompt := st.chat_input("اكتب فكرة مشروعك أو إجابتك هنا..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="👤"):
        st.write(prompt)
    save_to_db("user", prompt)

    with st.chat_message("assistant", avatar="🤖"):
        with st.spinner("جاري تحليل المتطلبات وصياغة السؤال التالي..."):
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=st.session_state.messages,
                temperature=0.4
            )
            reply = response.choices[0].message.content
            
            st.write(reply)
            st.session_state.messages.append({"role": "assistant", "content": reply})
            save_to_db("assistant", reply)
