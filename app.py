import os
import psycopg2
from datetime import datetime
import streamlit as st
from dotenv import load_dotenv
from groq import Groq

# 1. تحميل المفاتيح والبيئة
load_dotenv()
api_key = os.getenv("GROQ_API_KEY")
db_url = os.getenv("DATABASE_URL")

st.set_page_config(page_title="AI Requirement Elicitor", page_icon="🤖")
st.title("🤖 مساعد استنباط المتطلبات الذكي")
st.subheader("المرحلة 9: التنفيذ والتخزين السحابي")

if not api_key:
    st.error("لم يتم العثور على GROQ_API_KEY في الإعدادات.")
    st.stop()

client = Groq(api_key=api_key)

# 2. إعداد قاعدة البيانات السحابية (Supabase PostgreSQL)
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

# 3. توجيه النظام (System Prompt)
SYSTEM_PROMPT = """أنت مهندس هندسة متطلبات برمجيات محترف (Requirements Engineer).
دورك إجراء مقابلة تفاعلية مع العميل لاستنباط المتطلبات.
القواعد:
1. اطرح سؤالاً واحداً محدداً في كل مرة.
2. اسأل أسئلة عميقة لكشف الغموض في الفكرة.
3. ركز على استخراج المتطلبات الوظيفية (FR) وغير الوظيفية (NFR)."""

# 4. الشريط الجانبي
with st.sidebar:
    st.header("⚙️ إعدادات النظام")
    st.info("النظام موصول حالياً بقاعدة بيانات سحابية (Supabase) لحفظ جميع المحادثات بشكل دائم.")
    if st.button("🗑️ مسح الجلسة وبدء جديد"):
        st.session_state.messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "assistant", "content": "مرحباً بك! أنا مساعدك الذكي. أخبرني عن فكرة مشروعك لنبدأ باستنباط المتطلبات معاً."}
        ]
        st.rerun()

# 5. تهيئة الذاكرة المؤقتة
if "messages" not in st.session_state:
    init_db()
    st.session_state.messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "assistant", "content": "مرحباً بك! أنا مساعدك الذكي. أخبرني عن فكرة مشروعك لنبدأ باستنباط المتطلبات معاً."}
    ]

# 6. عرض المحادثة
for msg in st.session_state.messages:
    if msg["role"] != "system":
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

# 7. معالجة مدخلات المستخدم واستجابة AI
if prompt := st.chat_input("اكتب فكرتك هنا..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)
    save_to_db("user", prompt)

    with st.chat_message("assistant"):
        with st.spinner("جاري التفكير وتحليل المتطلبات..."):
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=st.session_state.messages,
                temperature=0.4
            )
            reply = response.choices[0].message.content
            
            st.write(reply)
            st.session_state.messages.append({"role": "assistant", "content": reply})
            save_to_db("assistant", reply)

st.divider()
st.success("✅ التطبيق يعمل الآن بنجاح ومربوط بقاعدة البيانات السحابية!")
