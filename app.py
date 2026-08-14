import os
import sqlite3
from datetime import datetime
import streamlit as st
from dotenv import load_dotenv
from groq import Groq

# 1. تحميل المفاتيح وإعداد الصفحة
load_dotenv()
api_key = os.getenv("GROQ_API_KEY")

st.set_page_config(page_title="AI Requirement Elicitor", page_icon="🤖")
st.title("🤖 مساعد استنباط المتطلبات الذكي")
st.subheader("المرحلة 9: التنفيذ والبرمجة")

if not api_key:
    st.error("لم يتم العثور على GROQ_API_KEY في ملف .env. يرجى إضافته أولاً.")
    st.stop()

client = Groq(api_key=api_key)

# 2. إعدادات قاعدة البيانات SQLite
def init_db():
    conn = sqlite3.connect('project_data.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS chat_logs 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  role TEXT, 
                  content TEXT, 
                  timestamp TEXT)''')
    conn.commit()
    conn.close()

def save_to_db(role, content):
    conn = sqlite3.connect('project_data.db')
    c = conn.cursor()
    c.execute("INSERT INTO chat_logs (role, content, timestamp) VALUES (?, ?, ?)",
              (role, content, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

# 3. الشريط الجانبي (Sidebar)
with st.sidebar:
    st.header("⚙️ إعدادات النظام")
    st.info("يستخدم هذا النظام LLM عبر Groq API لاستنباط المتطلبات مع حفظ الجلسة محلياً في SQLite.")
    if st.button("🗑️ مسح الجلسة وبدء جديد"):
        st.session_state.messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "assistant", "content": "مرحباً بك! أنا مساعدك الذكي. أخبرني عن فكرة مشروعك لنبدأ باستنباط المتطلبات معاً."}
        ]
        st.rerun()

# 4. توجيه النظام (System Prompt) وتهيئة الذاكرة
SYSTEM_PROMPT = """أنت مهندس هندسة متطلبات برمجيات محترف (Requirements Engineer).
دورك إجراء مقابلة تفاعلية مع العميل لاستنباط المتطلبات.
القواعد:
1. اطرح سؤالاً واحداً محدداً في كل مرة.
2. اسأل أسئلة عميقة لكشف الغموض المتواجد في الفكرة.
3. ركز على استخراج المتطلبات الوظيفية (FR) وغير الوظيفية (NFR)."""

if "messages" not in st.session_state:
    init_db()
    st.session_state.messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "assistant", "content": "مرحباً بك! أنا مساعدك الذكي. أخبرني عن فكرة مشروعك لنبدأ باستنباط المتطلبات معاً."}
    ]

# 5. عرض المحادثة (تجاهل تعليمات النظام المخفية)
for msg in st.session_state.messages:
    if msg["role"] != "system":
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

# 6. استقبال المدخلات وتوليد الرد الحقيقي عبر Groq
if prompt := st.chat_input("اكتب فكرتك هنا..."):
    # أ. حفظ وعرض رسالة المستخدم
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)
    save_to_db("user", prompt)

    # ب. توليد الرد المباشر من LLM
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
st.success("✅ النظام يعمل الآن مع خاصية التخزين (SQLite) واستجابة Groq الفعالة.")