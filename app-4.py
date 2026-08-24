import os 
import io 
import json 
import zipfile 
import html 
import uuid 
import psycopg2 
from psycopg2 import pool 
from datetime import datetime 
import streamlit as st 
from dotenv import load_dotenv 
from groq import Groq 
 
# 1. تحميل المفاتيح والبيئة 
load_dotenv() 
api_key = os.getenv("GROQ_API_KEY") 
db_url = os.getenv("DATABASE_URL") 
 
st.set_page_config(page_title="AI Requirement Elicitor", page_icon="😎") 
st.title("❄مساعد استنباط المتطلبات الذكي") 
 
USER_AVATAR = "🧑‍💻" 
ASSISTANT_AVATAR = "⚡" 
st.subheader("المرحلة 9: التنفيذ والتخزين السحابي") 
 
# CSS عام: نجعل مربع إدخال الشات يبدأ من اليمين (متوافق مع اتجاه اللغة العربية) 
st.markdown(""" 
<style> 
[data-testid="stChatInput"] textarea { 
    direction: rtl; 
    text-align: right; 
} 
</style> 
""", unsafe_allow_html=True) 
 
 
def render_bubble(role: str, content: str): 
    """يعرض رسالة المستخدم كفقاعة (يمين)، ويعرض رد المساعد كنص عادي بدون فقاعة (شمال).""" 
    is_user = role == "user" 
    safe_text = html.escape(content).replace("\n", "<br>") 
 
    if is_user: 
        st.markdown(f""" 
        <div style="display:flex; width:100%; justify-content:flex-end; margin:10px 0;"> 
            <div style="display:flex; flex-direction:row-reverse; align-items:flex-start; gap:8px; max-width:75%;"> 
                <div style="font-size:26px; line-height:1;">{USER_AVATAR}</div> 
                <div style="background-color:#DCF8C6; padding:10px 14px; border-radius:14px; 
                            direction:rtl; text-align:right; line-height:1.7; font-size:16px;"> 
                    {safe_text} 
                </div> 
            </div> 
        </div> 
        """, unsafe_allow_html=True) 
    else: 
        st.markdown(f""" 
        <div style="display:flex; width:100%; justify-content:flex-start; margin:10px 0;"> 
            <div style="display:flex; flex-direction:row; align-items:flex-start; gap:8px; max-width:75%;"> 
                <div style="font-size:26px; line-height:1;">{ASSISTANT_AVATAR}</div> 
                <div style="direction:rtl; text-align:right; line-height:1.7; font-size:16px; padding-top:4px;"> 
                    {safe_text} 
                </div> 
            </div> 
        </div> 
        """, unsafe_allow_html=True) 
 
 
 
if not api_key: 
    st.error("لم يتم العثور على GROQ_API_KEY في الإعدادات.") 
    st.stop() 
 
if not db_url: 
    st.error("لم يتم العثور على DATABASE_URL في الإعدادات.") 
    st.stop() 
 
client = Groq(api_key=api_key) 
 
# 2. إعداد قاعدة البيانات السحابية (Supabase PostgreSQL) 
# استخدام connection pool بدل فتح اتصال جديد مع كل عملية 
@st.cache_resource 
def get_connection_pool(): 
    try: 
        return psycopg2.pool.SimpleConnectionPool(1, 5, db_url) 
    except Exception as e: 
        st.error(f"تعذر إنشاء مجمّع الاتصالات بقاعدة البيانات: {e}") 
        return None 
 
 
def init_db(): 
    """تهيئة الجدول. يعيد True لو نجحت العملية أو كان الجدول موجوداً بالفعل.""" 
    conn_pool = get_connection_pool() 
    if conn_pool is None: 
        return False 
 
    conn = None 
    try: 
        conn = conn_pool.getconn() 
        with conn.cursor() as c: 
            c.execute('''CREATE TABLE IF NOT EXISTS chat_logs 
                         (id SERIAL PRIMARY KEY, 
                          session_id TEXT, 
                          role TEXT, 
                          content TEXT, 
                          timestamp TIMESTAMP)''') 
            # في حالة كان الجدول موجوداً من قبل بدون عمود session_id، نضيفه 
            c.execute('''ALTER TABLE chat_logs ADD COLUMN IF NOT EXISTS session_id TEXT''') 
        conn.commit() 
        return True 
    except Exception as e: 
        if conn: 
            conn.rollback() 
        st.error(f"خطأ في الاتصال بقاعدة البيانات السحابية: {e}") 
        return False
    finally: 
        if conn: 
            conn_pool.putconn(conn) 
 
 
def save_to_db(session_id, role, content): 
    """يحفظ الرسالة في قاعدة البيانات، ويظهر تحذيراً غير معطّل للتطبيق عند الفشل.""" 
    conn_pool = get_connection_pool() 
    if conn_pool is None: 
        return 
 
    conn = None 
    try: 
        conn = conn_pool.getconn() 
        with conn.cursor() as c: 
            c.execute( 
                "INSERT INTO chat_logs (session_id, role, content, timestamp) VALUES (%s, %s, %s, %s)", 
                (session_id, role, content, datetime.now()), 
            ) 
        conn.commit() 
    except Exception as e: 
        if conn: 
            conn.rollback() 
        # لا نوقف التطبيق بسبب فشل الحفظ، فقط نسجل الخطأ 
        print(f"خطأ في حفظ البيانات: {e}") 
        st.toast(f"⚠️ تعذر حفظ الرسالة في قاعدة البيانات: {e}", icon="⚠️") 
    finally: 
        if conn: 
            conn_pool.putconn(conn) 
 
 
def list_sessions(): 
    """يرجع قائمة بالجلسات السابقة: session_id، أول رسالة مستخدم فيها (كعنوان)، وآخر توقيت.""" 
    conn_pool = get_connection_pool() 
    if conn_pool is None: 
        return [] 
 
    conn = None 
    try: 
        conn = conn_pool.getconn() 
        with conn.cursor() as c: 
            c.execute(''' 
                SELECT session_id, 
                       MIN(timestamp) AS started_at, 
                       (SELECT content FROM chat_logs c2 
                        WHERE c2.session_id = c1.session_id AND c2.role = 'user' 
                        ORDER BY c2.timestamp ASC LIMIT 1) AS first_user_msg 
                FROM chat_logs c1 
                WHERE session_id IS NOT NULL 
                GROUP BY session_id 
                ORDER BY started_at DESC 
                LIMIT 30 
            ''') 
            rows = c.fetchall() 
        return rows 
    except Exception as e: 
        print(f"خطأ في جلب قائمة الجلسات: {e}") 
        return [] 
    finally: 
        if conn: 
            conn_pool.putconn(conn) 
 
 
def load_session_messages(session_id): 
    """يجلب كل رسائل جلسة معينة من قاعدة البيانات ويحولها لصيغة session_state.messages.""" 
    conn_pool = get_connection_pool() 
    if conn_pool is None: 
        return None 
 
    conn = None 
    try: 
        conn = conn_pool.getconn() 
        with conn.cursor() as c: 
            c.execute( 
                "SELECT role, content FROM chat_logs WHERE session_id = %s ORDER BY timestamp ASC", 
                (session_id,), 
            ) 
            rows = c.fetchall() 
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] 
        messages.extend({"role": r, "content": c_} for r, c_ in rows) 
        return messages 
    except Exception as e: 
        print(f"خطأ في تحميل الجلسة: {e}") 
        return None 
    finally: 
        if conn: 
            conn_pool.putconn(conn) 
 
 
# 3. توجيه النظام (System Prompt) 
SYSTEM_PROMPT = """أنت مهندس هندسة متطلبات برمجيات محترف (Requirements Engineer). 
دورك إجراء مقابلة تفاعلية مع العميل لاستنباط المتطلبات. 
القواعد: 
1. اطرح سؤالاً واحداً محدداً في كل مرة. 
2. اسأل أسئلة عميقة لكشف الغموض في الفكرة. 
3. ركز على استخراج المتطلبات الوظيفية (FR) وغير الوظيفية (NFR).""" 
 
WELCOME_MESSAGE = "مرحباً بك! أنا مساعدك الذكي. أخبرني عن فكرة مشروعك لنبدأ باستنباط المتطلبات معاً."

# System Prompt خاص بتحويل المحادثة إلى تقرير متطلبات نهائي شامل، مقسم كأجزاء منفصلة
REQUIREMENTS_EXTRACTION_PROMPT = """أنت مهندس متطلبات محترف. مهمتك الآن مختلفة: لا تسأل أسئلة، بل حلّل كل المحادثة السابقة بين المحلل والعميل، وابنِ منها وثائق متطلبات منفصلة.

أخرج النتيجة بصيغة JSON فقط (بدون Markdown fences، وبدون أي نص قبلها أو بعدها). الكائن JSON يجب أن يحتوي بالضبط على هذه المفاتيح، وكل قيمة تكون نص Markdown كامل وجاهز للحفظ في ملف .md منفصل:

{
  "overview": "محتوى ملف README.md: عنوان المشروع، فقرة نظرة عامة (2-3 أسطر)، وفهرس مختصر يشرح محتوى كل ملف في المجلد",
  "functional_requirements": "محتوى ملف functional_requirements.md: عنوان + جدول Markdown بالأعمدة (الرقم، المتطلب، الوصف) بترقيم FR-1, FR-2...",
  "non_functional_requirements": "محتوى ملف non_functional_requirements.md: عنوان + جدول Markdown بالأعمدة (الرقم، المتطلب، الوصف) بترقيم NFR-1, NFR-2...",
  "use_cases": "محتوى ملف use_cases.md: عنوان + لكل حالة استخدام (UC-1, UC-2...): الفاعل، الهدف، السيناريو الأساسي كخطوات مرقمة، والمتطلب الوظيفي المرتبط بها",
  "user_stories": "محتوى ملف user_stories.md: عنوان + قائمة نقطية بصيغة (كـ[نوع المستخدم]، أريد [الهدف]، لكي [القيمة]) بترقيم US-1, US-2... مع ربط كل قصة بالمتطلب المرتبط بها",
  "report": "محتوى ملف report.md: التقرير النهائي الشامل الذي يجمع كل الأقسام أعلاه بالكامل (نظرة عامة، المتطلبات الوظيفية، غير الوظيفية، حالات الاستخدام، قصص المستخدم) بالإضافة لقسمين إضافيين في النهاية: نقاط تحتاج توضيحاً إضافياً، وخلاصة نهائية"
}

قواعد صارمة:
- استخرج فقط ما هو مذكور فعلياً أو مستنتج بوضوح من كلام العميل، لا تختلق متطلبات أو حالات استخدام غير مطروحة.
- لو لم تتوفر معلومات كافية لقسم معين، اكتب سطراً واحداً يقول "لم يتم تحديده بعد في المحادثة" بدل ترك القسم فارغاً أو حذف المفتاح.
- كل قيمة يجب أن تبدأ بعنوان Markdown (#) مناسب لاسم الملف.
- أخرج JSON صالح (valid) قابل للتحليل مباشرة بدون أي أخطاء صياغية، ولا تستخدم علامات"""
 
 
def generate_requirements_document(messages):

    """يبني وثائق متطلبات منفصلة (JSON) من كامل المحادثة الحالية عبر نموذج الذكاء الاصطناعي.
    يرجع dict فيه المفاتيح: overview, functional_requirements, non_functional_requirements,
    use_cases, user_stories, report."""

    conversation_only = [m for m in messages if m["role"] in ("user", "assistant")]

    if not conversation_only:
        return None

    api_messages = [{"role": "system", "content": REQUIREMENTS_EXTRACTION_PROMPT}]
    api_messages.extend(conversation_only)

    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=api_messages,
        temperature=0.2,
    )
    raw = response.choices[0].message.content.strip()

    """ حماية إضافية: لو النموذج غلّف الناتج بـ 
json رغم التعليمات، نشيلها قبل التحليل"""
    if raw.startswith("`"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    return json.loads(raw)


def build_requirements_zip(docs: dict, folder_name: str = "Requirements") -> bytes:
    """يحزم dict الوثائق في ملف ZIP واحد بهيكل مجلد Requirements/ يحتوي كل ملف .md على حدة."""
    file_map = {
        "README.md": docs.get("overview", ""),
        "functional_requirements.md": docs.get("functional_requirements", ""),
        "non_functional_requirements.md": docs.get("non_functional_requirements", ""),
        "use_cases.md": docs.get("use_cases", ""),
        "user_stories.md": docs.get("user_stories", ""),
        "report.md": docs.get("report", ""),
    }

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for filename, content in file_map.items():
            zf.writestr(f"{folder_name}/{filename}", content or "")
    buffer.seek(0)
    return buffer.getvalue()


def new_session(): 
    return [ 
        {"role": "system", "content": SYSTEM_PROMPT}, 
        {"role": "assistant", "content": WELCOME_MESSAGE}, 
    ] 
 
 
# 4. تهيئة الذاكرة المؤقتة (يجب أن تحدث قبل عرض الشريط الجانبي حتى تعمل قائمة الجلسات من أول تحميل) 
if "messages" not in st.session_state: 
    st.session_state.db_ready = init_db() 
    st.session_state.session_id = str(uuid.uuid4()) 
    st.session_state.messages = new_session() 
 
# 5. الشريط الجانبي 
with st.sidebar: 
    st.header("⚙️ إعدادات النظام") 
    st.info("النظام موصول حالياً بقاعدة بيانات سحابية (Supabase) لحفظ جميع المحادثات بشكل دائم.") 
 
    if st.button("New بدء جلسة جديد"):
     st.session_state.session_id = str(uuid.uuid4()) 
     st.session_state.messages = new_session() 
     st.rerun() 
 
    st.divider() 
    st.subheader("📂 الجلسات السابقة") 
    sessions = list_sessions() if st.session_state.get("db_ready", False) else [] 
 
    if not sessions: 
        st.caption("لا توجد جلسات محفوظة بعد.") 
    else: 
        for sid, started_at, first_msg in sessions: 
            label = (first_msg or "بدون عنوان")[:35] 
            time_label = started_at.strftime("%Y-%m-%d %H:%M") if started_at else "" 
            is_current = sid == st.session_state.get("session_id") 
            button_label = f"{'🟢 ' if is_current else ''}{label}\n{time_label}" 
            if st.button(button_label, key=f"session_{sid}"): 
                loaded = load_session_messages(sid) 
                if loaded: 
                    st.session_state.session_id = sid 
                    st.session_state.messages = loaded 
                    st.rerun() 
 
    if not st.session_state.get("db_ready", False): 
        st.warning("⚠️ قاعدة البيانات غير متاحة حالياً، المحادثة لن تُحفظ بشكل دائم.") 
 
# 6. عرض المحادثة 
chat_container = st.container() 
 
with chat_container: 
    for msg in st.session_state.messages: 
        if msg["role"] != "system": 
            render_bubble(msg["role"], msg["content"]) 
 
# 7. معالجة مدخلات المستخدم واستجابة AI 
if prompt := st.chat_input("اكتب فكرتك هنا..."): 
    st.session_state.messages.append({"role": "user", "content": prompt}) 
    with chat_container: 
        render_bubble("user", prompt) 
    save_to_db(st.session_state.session_id, "user", prompt) 
 
    with chat_container: 
        with st.spinner("جاري التفكير وتحليل المتطلبات..."): 
            try: 
                response = client.chat.completions.create( 
                    model="openai/gpt-oss-120b", 
                    messages=st.session_state.messages, 
                    temperature=0.4, 
                ) 
                reply = response.choices[0].message.content 
            except Exception as e: 
                reply = None 
                st.error(f"حدث خطأ أثناء الاتصال بنموذج الذكاء الاصطناعي: {e}") 
 
            if reply: 
                render_bubble("assistant", reply) 
                st.session_state.messages.append({"role": "assistant", "content": reply}) 
                save_to_db(st.session_state.session_id, "assistant", reply) 
 
st.divider() 
 
# 8. توليد التقرير النهائي الشامل كملفات منفصلة (Requirements/ folder) 
st.subheader("📄 التقرير النهائي للمتطلبات") 
st.caption("يولّد مجلد Requirements/ فيه: README، المتطلبات الوظيفية وغير الوظيفية، حالات الاستخدام، قصص المستخدم، والتقرير النهائي — كل واحد ملف .md منفصل.") 
 
col1, col2 = st.columns([1, 3]) 
with col1: 
    extract_clicked = st.button("📄 توليد التقرير النهائي") 
 
if extract_clicked: 
    with st.spinner("جاري تحليل المحادثة وبناء الملفات..."): 
        try: 
            docs = generate_requirements_document(st.session_state.messages) 
            if docs: 
                st.session_state.requirements_docs = docs 
            else: 
                st.warning("لا توجد محادثة كافية بعد لبناء التقرير منها.") 
        except json.JSONDecodeError as e: 
            st.error(f"تعذّر تحليل استجابة النموذج كـ JSON، حاول مرة أخرى: {e}") 
        except Exception as e: 
            st.error(f"حدث خطأ أثناء بناء التقرير: {e}") 
 
if st.session_state.get("requirements_docs"): 
    docs = st.session_state.requirements_docs 
 
    zip_bytes = build_requirements_zip(docs) 
    st.download_button( 
        label="⬇️ تحميل مجلد Requirements كاملاً (ZIP)", 
        data=zip_bytes, 
        file_name=f"Requirements_{st.session_state.session_id}.zip", 
        mime="application/zip", 
    ) 
 
    tabs = st.tabs(["README", "FR", "NFR", "Use Cases", "User Stories", "Report"])