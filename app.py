import random
import time
from pathlib import Path

import streamlit as st
from google import genai

# =========================
# SAYFA AYARLARI
# =========================
st.set_page_config(
    page_title="LGS AI Tutor",
    page_icon="🎓",
    layout="wide"
)

# =========================
# CSS
# =========================
st.markdown("""
<style>
.main-title {
    font-size: 2.2rem;
    font-weight: 800;
    margin-bottom: 0.2rem;
}
.subtle {
    color: #cbd5e1;
    margin-bottom: 1rem;
}
.badge {
    padding: 0.4rem 0.8rem;
    border-radius: 999px;
    background: #eef2ff;
    color: #111827;
    display: inline-block;
    margin-right: 0.5rem;
    margin-bottom: 0.5rem;
    font-weight: 600;
}
.score-box {
    padding: 1rem;
    border-radius: 16px;
    background: #f8fafc;
    color: #111827;
    border: 1px solid #e2e8f0;
}
.small-note {
    font-size: 0.9rem;
    color: #94a3b8;
}
</style>
""", unsafe_allow_html=True)

# =========================
# SESSION STATE
# =========================
def init_state():
    defaults = {
        "chat_history": [],
        "score": 0,
        "correct_count": 0,
        "wrong_count": 0,
        "quiz_count": 0,
        "visual_count": 0,
        "last_quiz": "",
        "current_visual_key": None,
        "student_name": "",
        "topic_stats": {},
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

# =========================
# YARDIMCI FONKSİYONLAR
# =========================
def get_badge(score: int) -> str:
    if score >= 120:
        return "🏆 LGS Ustası"
    if score >= 80:
        return "🥇 Altın Rozet"
    if score >= 50:
        return "🥈 Gümüş Rozet"
    if score >= 20:
        return "🥉 Bronz Rozet"
    return "📘 Başlangıç"

def update_topic_stat(topic, is_correct=None, quiz_done=False, visual_done=False):
    if topic not in st.session_state.topic_stats:
        st.session_state.topic_stats[topic] = {
            "correct": 0,
            "wrong": 0,
            "quiz": 0,
            "visual": 0
        }

    if is_correct is True:
        st.session_state.topic_stats[topic]["correct"] += 1
    elif is_correct is False:
        st.session_state.topic_stats[topic]["wrong"] += 1

    if quiz_done:
        st.session_state.topic_stats[topic]["quiz"] += 1

    if visual_done:
        st.session_state.topic_stats[topic]["visual"] += 1

def create_client():
    api_key = st.secrets.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        return None
    try:
        return genai.Client(api_key=api_key)
    except Exception:
        return None

def ask_gemini(client, prompt, model_name, max_retries=4):
    last_error = None

    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt
            )
            return response.text
        except Exception as e:
            last_error = e
            error_text = str(e)

            if "503" in error_text or "UNAVAILABLE" in error_text or "high demand" in error_text:
                wait_time = (2 ** attempt) + random.uniform(0.5, 1.5)
                time.sleep(wait_time)
            else:
                break

    raise last_error

def build_teacher_prompt(konu, seviye, mod, ders):
    mod_text = {
        "Konu Anlatımı": "Konuyu açık, net ve öğretici şekilde anlat.",
        "İpucu Ver": "Cevabı direkt verme, öğrenciyi ipuçlarıyla yönlendir.",
        "Adım Adım Çöz": "Soruyu adım adım çöz ve çözüm mantığını açıkla.",
        "Hızlı Tekrar": "Konunun en kritik noktalarını kısa ve öz şekilde özetle.",
        "Yeni Nesil Soru": "LGS tarzı düşünme gerektiren yeni nesil soru mantığıyla açıkla."
    }.get(mod, "Konuyu anlaşılır şekilde anlat.")

    return f"""
Sen LGS hazırlığında olan 8. sınıf öğrencilerine yardımcı olan sabırlı ve bilgili bir AI öğretmensin.

Kurallar:
- Türkçe konuş.
- 8. sınıf seviyesine uygun anlat.
- Gerekirse kısa konu özeti ver.
- Yeni nesil soru mantığını dikkate al.
- Fazla çocukça konuşma.
- Gerektiğinde örnek ver.
- Gerektiğinde çözüm stratejisi sun.
- Konu dışına çıkma.
- Cevapları düzenli ve okunaklı ver.

Ders: {ders}
Konu: {konu}
Seviye: {seviye}
Mod: {mod}

Öğretim tarzı:
{mod_text}
"""

def generate_quiz_with_ai(client, ders, konu, seviye, model_name):
    prompt = f"""
Sen LGS düzeyinde soru hazırlayan deneyimli bir öğretmensin.

Ders: {ders}
Konu: {konu}
Seviye: {seviye}

Bu konu için 3 soruluk mini quiz hazırla.

Kurallar:
- Sorular 8. sınıf / LGS düzeyinde olsun.
- Mümkünse yeni nesil soru tarzında olsun.
- Her soru 4 seçenekli olsun.
- Önce sadece soruları yaz.
- Sonra ayrı bir satıra tam olarak şunu yaz:
===CEVAP_ANAHTARI===
- Bu başlığın altına cevap anahtarını yaz.
- İstersen her soru için çok kısa çözüm notu ekle.
- Türkçe ve düzenli yaz.
"""
    return ask_gemini(client, prompt, model_name)

def get_fallback_quiz(konu):
    return (
        f"1) {konu} konusunda temel bilgi gerektiren bir soru\n"
        f"A) ...\nB) ...\nC) ...\nD) ...\n\n"
        f"2) {konu} konusunda yeni nesil mantık içeren bir soru\n"
        f"A) ...\nB) ...\nC) ...\nD) ...\n\n"
        f"3) {konu} ile ilgili yorumlama sorusu\n"
        f"A) ...\nB) ...\nC) ...\nD) ...\n\n"
        f"===CEVAP_ANAHTARI===\n"
        f"1) A\n"
        f"2) C\n"
        f"3) B"
    )

def get_weak_topic():
    if not st.session_state.topic_stats:
        return None

    weakest_topic = None
    worst_score = None

    for topic, stats in st.session_state.topic_stats.items():
        total = stats["correct"] + stats["wrong"]
        if total == 0:
            continue
        success = stats["correct"] / total
        if worst_score is None or success < worst_score:
            worst_score = success
            weakest_topic = topic

    return weakest_topic

def build_daily_plan(ders, konu):
    return f"""
**Bugünkü {konu} Çalışma Planı**
1. 15 dk konu özeti oku
2. 10 dk temel örnek çöz
3. 15 dk yeni nesil soru çöz
4. 10 dk yanlışlarını kontrol et
5. 5 dk kısa tekrar yap
"""

# =========================
# VERİLER
# =========================
LESSON_TOPICS = {
    "Matematik": [
        "Çarpanlar ve Katlar",
        "Üslü İfadeler",
        "Kareköklü İfadeler",
        "Cebirsel İfadeler",
        "Doğrusal Denklemler",
        "Eşitsizlikler",
        "Veri Analizi",
        "Olasılık"
    ],
    "Fen Bilimleri": [
        "Mevsimler ve İklim",
        "DNA ve Genetik Kod",
        "Basınç",
        "Madde ve Endüstri",
        "Basit Makineler",
        "Enerji Dönüşümleri",
        "Elektrik Yükleri ve Elektrik Enerjisi"
    ],
    "Türkçe": [
        "Paragraf Soruları",
        "Sözel Mantık",
        "Fiilimsi",
        "Cümlenin Öğeleri",
        "Yazım Kuralları",
        "Noktalama İşaretleri"
    ],
    "İnkılap Tarihi": [
        "Bir Kahraman Doğuyor",
        "Milli Uyanış",
        "Ya İstiklal Ya Ölüm",
        "Çağdaş Türkiye Yolunda Adımlar"
    ],
    "İngilizce": [
        "Friendship",
        "Teen Life",
        "In The Kitchen",
        "On The Phone",
        "The Internet"
    ]
}

OFFLINE_HINTS = {
    "Üslü İfadeler": "Üslü ifadelerde taban ve üs kavramlarına dikkat et. Üs, sayının kaç kez kendisiyle çarpıldığını gösterir.",
    "Kareköklü İfadeler": "Karekök içindeki sayının tam kare olup olmadığını kontrol et.",
    "Cebirsel İfadeler": "Benzer terimleri bir araya getir. Katsayılara dikkat et.",
    "Doğrusal Denklemler": "Bilinmeyeni yalnız bırak. Eşitliğin iki tarafına aynı işlemi uygula.",
    "Olasılık": "İstenen durum / tüm durum mantığını kullan.",
    "DNA ve Genetik Kod": "Gen, DNA ve kromozom kavramlarını karıştırma.",
    "Basınç": "Katı, sıvı ve gaz basıncı farklı mantıklarla incelenir.",
    "Basit Makineler": "Kuvvet kazancı olabilir ama işten kazanç yoktur.",
    "Paragraf Soruları": "Ana düşünce ve yardımcı düşünceleri ayır.",
    "Fiilimsi": "Fiilimsi eklerine ve cümledeki görevine dikkat et.",
    "Sözel Mantık": "Verilen koşulları tabloya dökerek ilerlemek işini kolaylaştırır."
}

OFFLINE_EXAMPLES = {
    "Üslü İfadeler": "2³ = 2 x 2 x 2 = 8",
    "Kareköklü İfadeler": "√49 = 7",
    "Cebirsel İfadeler": "3x + 2x = 5x",
    "Doğrusal Denklemler": "x + 5 = 12 ise x = 7",
    "Olasılık": "Bir torbada 5 kırmızı, 5 mavi top varsa kırmızı çekme olasılığı 5/10'dur.",
    "DNA ve Genetik Kod": "Kromozom, DNA'nın daha düzenli paketlenmiş hâlidir.",
    "Basınç": "Yüzey alanı küçülürse katı basıncı artar.",
    "Basit Makineler": "Makas, kaldıraç mantığıyla çalışan bir basit makinedir.",
    "Paragraf Soruları": "Parçada en çok vurgulanan düşünce ana fikirdir.",
    "Fiilimsi": "Koşmak sağlıklıdır cümlesindeki 'koşmak' isim-fiildir.",
    "Sözel Mantık": "Kısıtları tek tek yazarak eleme yöntemi kullanabilirsin."
}

VISUAL_QUESTIONS = [
    {
        "key": "uslu1",
        "topic": "Üslü İfadeler",
        "image": "images/uslu1.png",
        "question": "Görselde verilen ifadeye göre aşağıdakilerden hangisi doğrudur?",
        "options": ["2³ = 6", "2³ = 8", "3² = 5", "2² = 8"],
        "answer": "2³ = 8",
        "explanation": "2³, 2 sayısının 3 kez kendisiyle çarpılmasıdır: 2 x 2 x 2 = 8."
    },
    {
        "key": "grafik1",
        "topic": "Veri Analizi",
        "image": "images/grafik1.png",
        "question": "Grafiğe göre en yüksek değere sahip kategori hangisidir?",
        "options": ["A", "B", "C", "D"],
        "answer": "B",
        "explanation": "Grafikte en yüksek sütun B kategorisine aittir."
    },
    {
        "key": "dna1",
        "topic": "DNA ve Genetik Kod",
        "image": "images/dna1.png",
        "question": "Görselde gösterilen yapı aşağıdakilerden hangisidir?",
        "options": ["Kromozom", "Mitokondri", "Ribozom", "Hücre Zarı"],
        "answer": "Kromozom",
        "explanation": "X şeklinde gösterilen yapı kromozomdur."
    },
    {
    "key": "paragraf1",
    "topic": "Paragraf Soruları",
    "image": "images/paragraf1.png",
    "question": "Bu metinde aşağıdakilerden hangisinden söz edilmektedir?",
    "options": [
        "Edebiyatla tanışan çocuğun neler kazandığından",
        "Bol resimli edebi metinlerin ilgi görmesinden",
        "Edebiyat sevgisinin çocuğun içinde olması gerektiğinden",
        "Yazarın yeni bir edebiyat nesli yetiştirmek istemesinden"
    ],
    "answer": "Edebiyatla tanışan çocuğun neler kazandığından",
    "explanation": "Paragrafta çocukların edebiyat sayesinde dünyayı, hayatı ve hayalleri deneyimlediği; bir şeyler öğrenirken kendilerini tanıdığı anlatılıyor."
}
]

# =========================
# BAŞLANGIÇ
# =========================
init_state()
client = create_client()

# =========================
# SIDEBAR
# =========================
with st.sidebar:
    st.markdown("## ⚙️ Ayarlar")

    st.session_state.student_name = st.text_input(
        "Öğrenci adı",
        value=st.session_state.student_name
    )

    ders = st.selectbox("Ders seç", list(LESSON_TOPICS.keys()))
    konu = st.selectbox("Konu seç", LESSON_TOPICS[ders])
    seviye = st.selectbox("Zorluk seviyesi", ["Kolay", "Orta", "Zor"])
    mod = st.selectbox(
        "Çalışma modu",
        ["Konu Anlatımı", "İpucu Ver", "Adım Adım Çöz", "Hızlı Tekrar", "Yeni Nesil Soru"]
    )
    model_name = st.selectbox(
        "Model",
        ["gemini-2.5-flash", "gemini-2.0-flash"],
        index=0
    )

    st.markdown("---")
    st.markdown("### 📊 İlerleme")
    st.markdown(
        f"<div class='score-box'>"
        f"<b>Puan:</b> {st.session_state.score}<br>"
        f"<b>Rozet:</b> {get_badge(st.session_state.score)}<br>"
        f"<b>Doğru:</b> {st.session_state.correct_count}<br>"
        f"<b>Yanlış:</b> {st.session_state.wrong_count}<br>"
        f"<b>Quiz:</b> {st.session_state.quiz_count}<br>"
        f"<b>Görsel Soru:</b> {st.session_state.visual_count}"
        f"</div>",
        unsafe_allow_html=True
    )

    weak_topic = get_weak_topic()
    if weak_topic:
        st.warning(f"Geliştirilmesi gereken konu: {weak_topic}")

    st.markdown("---")
    if st.button("🧹 Tüm Geçmişi Sıfırla", width='stretch'):
        st.session_state.chat_history = []
        st.session_state.score = 0
        st.session_state.correct_count = 0
        st.session_state.wrong_count = 0
        st.session_state.quiz_count = 0
        st.session_state.visual_count = 0
        st.session_state.last_quiz = ""
        st.session_state.current_visual_key = None
        st.session_state.topic_stats = {}
        st.rerun()

# =========================
# HEADER
# =========================
student_line = f" - {st.session_state.student_name}" if st.session_state.student_name else ""
st.markdown(f"<div class='main-title'>🎓 LGS AI Tutor{student_line}</div>", unsafe_allow_html=True)
st.markdown(
    "<div class='subtle'>LGS hazırlığı için konu anlatımı, yeni nesil soru, quiz, görselli soru ve gelişim takibi.</div>",
    unsafe_allow_html=True
)

api_status = "🟢 AI bağlı" if client else "🟡 AI yok - temel mod çalışır"
st.markdown(
    f"<span class='badge'>{api_status}</span>"
    f"<span class='badge'>Ders: {ders}</span>"
    f"<span class='badge'>Konu: {konu}</span>"
    f"<span class='badge'>Seviye: {seviye}</span>"
    f"<span class='badge'>Mod: {mod}</span>",
    unsafe_allow_html=True
)

# =========================
# TABS
# =========================
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "💬 AI Öğretmen",
    "📝 Mini Quiz",
    "🖼️ Görsel Soru",
    "📈 Gelişim Kartı",
    "📅 Günlük Plan"
])

# =========================
# TAB 1 - SOHBET
# =========================
with tab1:
    st.subheader("AI Öğretmen ile Çalış")

    if not client:
        st.info("Gemini API anahtarı yoksa sistem temel açıklamalarla çalışır.")

    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    user_input = st.chat_input("Sorunu yaz veya konu hakkında yardım iste...")

    if user_input:
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        if client:
            prompt = build_teacher_prompt(konu, seviye, mod, ders) + f"\n\nÖğrenci sorusu:\n{user_input}"
            try:
                answer = ask_gemini(client, prompt, model_name)
            except Exception as e:
                hint = OFFLINE_HINTS.get(konu, f"{konu} konusunda temel kavramları tekrar et.")
                example = OFFLINE_EXAMPLES.get(konu, "Kısa bir örnek çözerek ilerle.")
                answer = f"AI şu anda yoğun olabilir.\n\n{hint}\n\nÖrnek:\n{example}\n\nHata: {e}"
        else:
            hint = OFFLINE_HINTS.get(konu, f"{konu} konusunda temel kavramları tekrar et.")
            example = OFFLINE_EXAMPLES.get(konu, "Kısa bir örnek çözerek ilerle.")
            answer = f"{hint}\n\nÖrnek:\n{example}"

        st.session_state.chat_history.append({"role": "assistant", "content": answer})
        with st.chat_message("assistant"):
            st.markdown(answer)

# =========================
# TAB 2 - QUIZ
# =========================
with tab2:
    st.subheader("Mini Quiz")

    col_q1, col_q2 = st.columns([1, 1])

    with col_q1:
        if st.button("🎯 LGS Quiz Oluştur", width='stretch'):
            if client:
                try:
                    st.session_state.last_quiz = generate_quiz_with_ai(client, ders, konu, seviye, model_name)
                except Exception:
                    st.warning("AI şu anda yoğun olabilir. Yedek quiz gösteriliyor.")
                    st.session_state.last_quiz = get_fallback_quiz(konu)
            else:
                st.session_state.last_quiz = get_fallback_quiz(konu)

    with col_q2:
        if st.button("✅ Quiz Çözdüm", width='stretch'):
            st.session_state.quiz_count += 1
            st.session_state.score += 5
            update_topic_stat(konu, quiz_done=True)
            st.success("Quiz tamamlandı. +5 puan")

    if st.session_state.last_quiz:
        st.markdown("### Quiz Çıktısı")

        if "===CEVAP_ANAHTARI===" in st.session_state.last_quiz:
            quiz_text, answer_key = st.session_state.last_quiz.split("===CEVAP_ANAHTARI===", 1)
            st.markdown(quiz_text.strip())

            with st.expander("🙈 Spoiler: Cevap anahtarını göster"):
                st.markdown(answer_key.strip())
        else:
            st.markdown(st.session_state.last_quiz)

# =========================
# TAB 3 - GÖRSEL SORU
# =========================
with tab3:
    st.subheader("Görsel / Grafik / Şema Soruları")

    topic_visuals = [q for q in VISUAL_QUESTIONS if q["topic"] == konu]
    if not topic_visuals:
        topic_visuals = VISUAL_QUESTIONS

    if st.button("🔀 Yeni Görsel Soru Getir", width='stretch'):
        selected = random.choice(topic_visuals)
        st.session_state.current_visual_key = selected["key"]

    current_question = None
    if st.session_state.current_visual_key:
        current_question = next(
            (q for q in VISUAL_QUESTIONS if q["key"] == st.session_state.current_visual_key),
            None
        )

    if current_question is None:
        current_question = random.choice(topic_visuals)
        st.session_state.current_visual_key = current_question["key"]

    image_path = Path(current_question["image"])

    col_img, col_form = st.columns([1.1, 1])

    with col_img:
        if image_path.exists():
            st.image(str(image_path), width='stretch')
        else:
            st.warning(f"Görsel bulunamadı: {current_question['image']}")

    with col_form:
        st.markdown(f"**Soru:** {current_question['question']}")
        selected_option = st.radio(
            "Cevabını seç",
            current_question["options"],
            key=f"visual_radio_{current_question['key']}"
        )

        if st.button("Cevabı Kontrol Et", width='stretch'):
            st.session_state.visual_count += 1
            update_topic_stat(konu, visual_done=True)

            if selected_option == current_question["answer"]:
                st.success("Doğru cevap 🎉")
                st.info(current_question["explanation"])
                st.session_state.score += 10
                st.session_state.correct_count += 1
                update_topic_stat(konu, is_correct=True)
            else:
                st.error(f"Yanlış. Doğru cevap: {current_question['answer']}")
                st.info(current_question["explanation"])
                st.session_state.wrong_count += 1
                update_topic_stat(konu, is_correct=False)

# =========================
# TAB 4 - GELİŞİM KARTI
# =========================
with tab4:
    st.subheader("Gelişim Kartı")

    col1, col2, col3 = st.columns(3)
    col1.metric("Toplam Puan", st.session_state.score)
    col2.metric("Doğru Sayısı", st.session_state.correct_count)
    col3.metric("Yanlış Sayısı", st.session_state.wrong_count)

    total_answered = st.session_state.correct_count + st.session_state.wrong_count
    success_rate = 0 if total_answered == 0 else round((st.session_state.correct_count / total_answered) * 100, 1)

    col4, col5, col6 = st.columns(3)
    col4.metric("Başarı Oranı", f"%{success_rate}")
    col5.metric("Çözülen Quiz", st.session_state.quiz_count)
    col6.metric("Rozet", get_badge(st.session_state.score))

    st.markdown("### Genel Yorum")
    if total_answered == 0 and st.session_state.quiz_count == 0:
        st.write("Henüz yeterli veri yok. Önce birkaç soru çöz.")
    elif success_rate >= 80:
        st.success("Çok iyi gidiyorsun. LGS düzeyinde sağlam ilerliyorsun.")
    elif success_rate >= 50:
        st.info("İyi gidiyorsun. Düzenli tekrar ile çok daha iyi seviyeye çıkabilirsin.")
    else:
        st.warning("Temel konuları tekrar etmen ve daha fazla örnek çözmen faydalı olur.")

    weak_topic = get_weak_topic()
    if weak_topic:
        st.markdown("### Tekrar Önerisi")
        st.write(f"En çok zorlandığın konu: **{weak_topic}**")
        if weak_topic in OFFLINE_HINTS:
            st.write(OFFLINE_HINTS[weak_topic])
        if weak_topic in OFFLINE_EXAMPLES:
            st.write(f"Örnek: {OFFLINE_EXAMPLES[weak_topic]}")

    if st.session_state.topic_stats:
        st.markdown("### Konu Bazlı Performans")
        for topic, stats in st.session_state.topic_stats.items():
            st.write(
                f"**{topic}** → "
                f"Doğru: {stats['correct']} | "
                f"Yanlış: {stats['wrong']} | "
                f"Quiz: {stats['quiz']} | "
                f"Görsel: {stats['visual']}"
            )

# =========================
# TAB 5 - GÜNLÜK PLAN
# =========================
with tab5:
    st.subheader("Günlük Çalışma Planı")

    if st.button("📅 Günlük Plan Oluştur", width='stretch'):
        if client:
            try:
                plan_prompt = f"""
Sen LGS hazırlığında olan 8. sınıf öğrencisi için günlük çalışma planı hazırlayan bir öğretmensin.

Ders: {ders}
Konu: {konu}
Seviye: {seviye}

Kurallar:
- Toplam çalışma süresi yaklaşık 40-50 dakika olsun.
- Konu tekrarı + örnek soru + yeni nesil soru + yanlış kontrol bölümleri olsun.
- Türkçe ve düzenli yaz.
"""
                plan = ask_gemini(client, plan_prompt, model_name)
                st.markdown(plan)
            except Exception:
                st.warning("AI yoğun olabilir. Yedek plan gösteriliyor.")
                st.markdown(build_daily_plan(ders, konu))
        else:
            st.markdown(build_daily_plan(ders, konu))

    st.markdown("### Çalışma Tavsiyesi")
    st.write(
        "Önce kısa konu tekrarı yap, sonra temel sorular çöz, ardından yeni nesil sorularla konuyu pekiştir."
    )
