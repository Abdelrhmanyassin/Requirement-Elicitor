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

# 2. تنسيق الواجهة (CSS)
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Arabic:wght@400;500;600;700&family=IBM+Plex+Mono:wght@500;600&display=swap');

html, body, [class*="css"] { font-family: 'IBM Plex Sans Arabic', sans-serif; }

[data-testid="stAppViewContainer"] { background:#F5F7F6; direction: rtl; }
[data-testid="stSidebar"] { background:#FFFFFF; }

.reb-hero{
  background:linear-gradient(135deg,#14293D 0%,#0D9488 150%);
  border-radius:16px; padding:22px 26px; margin-bottom:20px;
  display:flex; align-items:center; gap:16px; color:#F5F7F6;
}
.reb-hero .reb-icon{ font-size:32px; }
.reb-badge{
  font-family:'IBM Plex Mono',monospace; font-size:11px; letter-spacing:.08em;
  background:rgba(255,255,255,.16); padding:3px 10px; border-radius:999px;
}
.reb-hero h1{ font-size:21px; margin:8px 0 2px; font-weight:700; }
.reb-hero p{ margin:0; font-size:13px; opacity:.85; }

[data-testid="stChatMessage"]{
  background:#FFFFFF; border:1px solid #E4DFD3; border-radius:14px;
  padding:10px 14px; margin-bottom:10px;
  animation:reb-fade .25s ease-out;
}
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]){
  background:#0D9488; border-color:#0D9488; flex-direction:row-reverse;
}
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) p,
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) span{ color:#FFFFFF; }

@keyframes reb-fade{ from{opacity:0; transform:translateY(4px);} to{opacity:1; transform:translateY(0);} }
@media (prefers-reduced-motion: reduce){ [data-testid="stChatMessage"]{ animation:none; } }

.reb-status{
  display:flex; align-items:center; gap:8px; font-size:13px;
  padding:8px 10px; background:#F5F7F6; border-radius:10px; margin-bottom:8px;
}
.reb-dot{ width:8px; height:8px; border-radius:50%; background:#0D9488; flex-shrink:0; }
.reb-dot-off{ background:#D97706; }

[data-testid="stChatInput"] textarea{ font-family:'IBM Plex Sans Arabic',sans-serif; }
</style>
""", unsafe_allow_html=True)

if not api_key:
    st.error("لم يتم العثور على GROQ_API_KEY في الإعدادات.")
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
        return True
    except Exception as e:
        st.error(f"خطأ في الاتصال بقاعدة البيانات السحابية: {e}")
        return False


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

AVATARS = {"user": "🧑", "assistant": "🤖"}


def visible_messages():
    return [m for m in st.session_state.messages if m["role"] != "system"]


def fresh_session():
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "assistant",
         "content": "مرحباً بك! أنا مساعدك الذكي. أخبرني عن فكرة مشروعك لنبدأ باستنباط المتطلبات معاً.",
         "time": datetime.now().strftime("%H:%M")},
    ]


# 5. تهيئة الذاكرة المؤقتة
if "messages" not in st.session_state:
    st.session_state.db_connected = init_db()
    st.session_state.messages = fresh_session()

# 6. الشريط الجانبي
with st.sidebar:
    st.markdown("### ⚙️ إعدادات النظام")
    dot_class = "reb-dot" if st.session_state.db_connected else "reb-dot reb-dot-off"
    db_label = "متصلة" if st.session_state.db_connected else "غير متصلة"
    st.markdown(f"""
    <div class="reb-status"><span class="reb-dot"></span> Groq · llama-3.3-70b-versatile</div>
    <div class="reb-status"><span class="{dot_class}"></span> قاعدة البيانات: {db_label}</div>
    """, unsafe_allow_html=True)
    st.metric("عدد الرسائل", len(visible_messages()))
    st.divider()
    if st.button("🗑️ مسح الجلسة وبدء جديد", use_container_width=True):
        st.session_state.messages = fresh_session()
        st.rerun()
    with st.expander("عن المشروع"):

# 7. الترويسة (Header)
st.markdown("""
<div class="reb-hero">
  <div class="reb-icon">🤖</div>
  <div>
    <span class="reb-badge">WELCOME</span>
    <h1>AI Requirement Elicitor</h1>
  </div>
</div>
""", unsafe_allow_html=True)

# 8. عرض المحادثة
for i, msg in enumerate(visible_messages(), start=1):
    with st.chat_message(msg["role"], avatar=AVATARS.get(msg["role"], "💬")):
        st.write(msg["content"])
        st.caption(f"#{i:02d} · {msg.get('time', '')}")

# 9. معالجة مدخلات المستخدم واستجابة AI
if prompt := st.chat_input("اكتب فكرتك هنا..."):
    now = datetime.now().strftime("%H:%M")
    st.session_state.messages.append({"role": "user", "content": prompt, "time": now})
    with st.chat_message("user", avatar=AVATARS["user"]):
        st.write(prompt)
        st.caption(f"#{len(visible_messages()):02d} · {now}")
    save_to_db("user", prompt)

    with st.chat_message("assistant", avatar=AVATARS["assistant"]):
        with st.spinner("جاري التفكير وتحليل المتطلبات..."):
            # نرسل فقط role/content لـ Groq (بدون حقل "time" المضاف للعرض)
            api_messages = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages]
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=api_messages,
                temperature=0.4
            )
            reply = response.choices[0].message.content
            reply_time = datetime.now().strftime("%H:%M")
        st.write(reply)
        st.session_state.messages.append({"role": "assistant", "content": reply, "time": reply_time})
        st.caption(f"#{len(visible_messages()):02d} · {reply_time}")
    save_to_db("assistant", reply)
