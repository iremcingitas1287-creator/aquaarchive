import streamlit as st
import pandas as pd
import json
from datetime import datetime
%%writefile app.py
import streamlit as st
import pandas as pd
from supabase import create_client
import folium
from streamlit_folium import st_folium
from streamlit_autorefresh import st_autorefresh
import time, re, unicodedata

SUPABASE_URL = "https://opribxrhbcorxdqnjhbp.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9wcmlieHJoYmNvcnhkcW5qaGJwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzc5MTIwNjMsImV4cCI6MjA5MzQ4ODA2M30.YtcpMPCsup53mbafIYEOwna51DoiEw72TOkbeKcrxew"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

st.set_page_config(
    page_title="Su Yapıları Arşivi",
    page_icon="💧",
    layout="wide"
)

st.markdown("""
<style>
.stApp {
    background: linear-gradient(135deg, #efe3cf, #f8f0df);
    color: #33251c;
}

[data-testid="stSidebar"] {
    background-color: #d1b38b;
    border-right: 2px solid #8b6846;
}

h1, h2, h3 {
    font-family: Georgia, serif;
    color: #3e2b1f;
}

.main-title {
    background: linear-gradient(135deg, #8b6846, #b99062);
    padding: 14px 24px;
    border-radius: 18px;
    text-align: center;
    border: 1.5px solid #6f5136;
    margin-bottom: 18px;
    box-shadow: 0 4px 12px rgba(70, 45, 25, 0.18);
}

.main-title h1 {
    color: white;
    font-size: 32px;
    margin-bottom: 2px;
}

.main-title p {
    color: white;
    font-size: 14px;
    margin: 0;
}

.side-card {
    background: #fff8eb;
    border: 1px solid #b99a6e;
    border-radius: 14px;
    padding: 12px;
    margin-bottom: 12px;
    box-shadow: 0 2px 7px rgba(70, 45, 25, 0.10);
}

.row-card {
    background: #fffaf0;
    border: 1px solid #c6aa80;
    border-left: 6px solid #8b6846;
    border-radius: 12px;
    padding: 9px 13px;
    margin-bottom: 7px;
    box-shadow: 0 2px 6px rgba(70, 45, 25, 0.08);
}

.row-title {
    font-size: 18px;
    font-weight: 700;
    color: #3e2b1f;
    margin-bottom: 2px;
}

.row-meta {
    font-size: 13px;
    color: #6b5946;
}

.tag {
    display: inline-block;
    background: #8b6846;
    color: white;
    padding: 3px 8px;
    border-radius: 999px;
    font-size: 11px;
    margin-right: 5px;
}

.note-box {
    background: #f5ead7;
    border-left: 4px solid #8b6846;
    border-radius: 10px;
    padding: 10px;
    margin-bottom: 10px;
}

.tiny-note {
    font-size: 11px;
    color: #7a6650;
    background: #f5ead7;
    border-radius: 8px;
    padding: 8px;
    margin-top: 10px;
}

.stream-title {
    font-size: 17px;
    font-weight: 700;
    color: #3e2b1f;
    margin-bottom: 8px;
}

.delete-box {
    background: #fff0e8;
    border-left: 5px solid #b85c38;
    border-radius: 12px;
    padding: 10px;
    margin-top: 12px;
}
</style>
""", unsafe_allow_html=True)


def clean_filename(name):
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-zA-Z0-9_.-]", "_", name)


def parse_coordinate(coord_text):
    numbers = re.findall(r"-?\d+\.\d+|-?\d+", coord_text or "")
    if len(numbers) < 2:
        return None, None
    return float(numbers[0]), float(numbers[1])


def get_structures():
    try:
        r = supabase.table("structures").select("*").order("structure_name").execute()
        data = r.data if r.data else []
        return sorted(data, key=lambda x: (x.get("structure_name") or "").lower())
    except Exception as e:
        st.error(f"Yapılar alınamadı: {e}")
        return []


def get_photos():
    try:
        r = supabase.table("photos").select("*").order("id", desc=True).execute()
        return r.data if r.data else []
    except Exception as e:
        st.error(f"Fotoğraflar alınamadı: {e}")
        return []


def add_structure(record):
    r = supabase.table("structures").insert(record).execute()
    if r.data:
        return r.data[0]["id"]
    return None


def upload_photo(file, structure_id, structure_name):
    safe_name = clean_filename(file.name)
    path = f"{structure_id}_{int(time.time())}_{safe_name}"

    supabase.storage.from_("photos").upload(
        path,
        file.getvalue(),
        file_options={
            "content-type": file.type,
            "upsert": "true"
        }
    )

    photo_url = supabase.storage.from_("photos").get_public_url(path)

    supabase.table("photos").insert({
        "structure_id": structure_id,
        "structure_name": structure_name,
        "photo_url": photo_url,
        "caption": structure_name
    }).execute()


def delete_structure(structure_id):
    supabase.table("photos").delete().eq("structure_id", structure_id).execute()
    supabase.table("structures").delete().eq("id", structure_id).execute()


def google_maps_link(lat, lon):
    return f"https://www.google.com/maps?q={lat},{lon}"


def short_text(text, limit=100):
    if not text:
        return "Açıklama eklenmemiş."
    return text if len(text) <= limit else text[:limit] + "..."


def photos_for_structure(photos, row):
    sid = row.get("id")
    sname = row.get("structure_name", "")
    return [
        p for p in photos
        if p.get("structure_id") == sid or p.get("structure_name") == sname
    ]


st.markdown("""
<div class="main-title">
    <h1>💧 Su Yapıları Arşivi</h1>
    <p>Kültürel miras su yapıları için kalıcı belgeleme ve envanter sistemi</p>
</div>
""", unsafe_allow_html=True)


menu = st.sidebar.radio(
    "Menü",
    ["Yeni Yapı", "Envanter", "Harita", "Galeri"]
)

st.sidebar.markdown("""
<div class="note-box">
Yapılar ve fotoğraflar kalıcı olarak saklanır.
</div>
""", unsafe_allow_html=True)


structures = get_structures()
photos = get_photos()

left_col, main_col, right_col = st.columns([1.05, 2.75, 1.25])


with left_col:
    st.subheader("📜 Arşiv Özeti")

    st.markdown(f"""
    <div class="side-card">
        <b>Yapı:</b> {len(structures)}<br>
        <b>Fotoğraf:</b> {len(photos)}<br>
        <b>Sistem:</b> Supabase
    </div>
    """, unsafe_allow_html=True)


    st.subheader("🏛️ Yapı Türleri")

    st.markdown("""
    <div class="side-card">
    Çeşme, sebil, şadırvan, sarnıç, su kemeri, su terazisi,
    maksem, maslak, bent/baraj, kuyu, ayazma, hamam, havuz,
    su yolu, kanal, depo, su kulesi, köprü, savak ve diğer yapılar.
    </div>
    """, unsafe_allow_html=True)


with main_col:

    if menu == "Yeni Yapı":
        st.subheader("➕ Yeni Yapı Kaydı")

        with st.form("new_structure_form"):
            added_by = st.text_input("Ekleyen kişi", placeholder="Örn: İrem")

            structure_name = st.text_input("Yapı adı")

            structure_type = st.selectbox(
                "Yapı türü",
                [
                    "Çeşme", "Sebil", "Şadırvan", "Sarnıç",
                    "Su Kemeri", "Su Terazisi", "Maksem", "Maslak",
                    "Bent / Baraj", "Kuyu", "Ayazma", "Hamam",
                    "Havuz", "Su Yolu / Galeri", "Kanal",
                    "Depo", "Su Kulesi", "Köprü", "Savak", "Diğer"
                ]
            )

            c1, c2 = st.columns(2)
            with c1:
                city = st.text_input("İl", value="İstanbul")
            with c2:
                district = st.text_input("İlçe")

            address = st.text_area("Adres")

            coordinate = st.text_input(
                "Koordinat",
                placeholder="Örnek: 41.008200, 28.978400"
            )

            description = st.text_area(
                "Metin bilgisi / açıklama",
                placeholder="Tarihçe, mimari özellik, malzeme, bozulma, restorasyon bilgisi veya kaynak notu yazabilirsin.",
                height=150
            )

            condition_status = st.selectbox(
                "Korunma durumu",
                ["İyi", "Orta", "Kötü", "Acil Müdahale Gerekli", "Bilinmiyor"]
            )

            uploaded_files = st.file_uploader(
                "Fotoğraf yükle",
                type=["jpg", "jpeg", "png"],
                accept_multiple_files=True
            )

            submitted = st.form_submit_button("Kaydı Kalıcı Olarak Ekle")

            if submitted:
                lat, lon = parse_coordinate(coordinate)

                if not added_by or not structure_name or not city or not district or not address:
                    st.warning("Ekleyen kişi, yapı adı, il, ilçe ve adres alanlarını doldur.")
                elif lat is None or lon is None:
                    st.warning("Koordinat formatı hatalı. Örnek: 41.008200, 28.978400")
                else:
                    try:
                        structure_id = add_structure({
                            "structure_name": structure_name,
                            "structure_type": structure_type,
                            "city": city,
                            "district": district,
                            "address": address,
                            "latitude": lat,
                            "longitude": lon,
                            "description": description,
                            "condition_status": condition_status,
                            "added_by": added_by
                        })

                        if structure_id and uploaded_files:
                            for file in uploaded_files:
                                upload_photo(file, structure_id, structure_name)

                        st.success("Yapı ve fotoğraflar kaydedildi.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Kayıt sırasında hata oluştu: {e}")

    elif menu == "Envanter":
        st.subheader("🏛️ Alfabetik Envanter")

        if not structures:
            st.info("Henüz kayıt yok.")
        else:
            df = pd.DataFrame(structures).sort_values(
                by="structure_name",
                key=lambda col: col.str.lower(),
                na_position="last"
            )

            c1, c2 = st.columns(2)

            with c1:
                filter_type = st.selectbox(
                    "Yapı türüne göre filtrele",
                    ["Tümü"] + sorted(df["structure_type"].dropna().unique().tolist())
                )

            with c2:
                people_filter = st.selectbox(
                    "Ekleyen kişiye göre filtrele",
                    ["Tümü"] + sorted(df["added_by"].dropna().unique().tolist())
                )

            search = st.text_input("Yapı adı, ilçe veya il ara")

            filtered = df.copy()

            if filter_type != "Tümü":
                filtered = filtered[filtered["structure_type"] == filter_type]

            if people_filter != "Tümü":
                filtered = filtered[filtered["added_by"] == people_filter]

            if search:
                filtered = filtered[
                    filtered["structure_name"].str.contains(search, case=False, na=False) |
                    filtered["district"].str.contains(search, case=False, na=False) |
                    filtered["city"].str.contains(search, case=False, na=False)
                ]

            for _, row in filtered.iterrows():
                related_photos = photos_for_structure(photos, row)

                st.markdown(f"""
                <div class="row-card">
                    <div class="row-title">{row.get("structure_name", "")}</div>
                    <div class="row-meta">
                        <span class="tag">{row.get("structure_type", "")}</span>
                        {row.get("city", "")} / {row.get("district", "")} ·
                        {row.get("condition_status", "")} ·
                        Ekleyen: @{row.get("added_by", "Belirtilmemiş")}
                    </div>
                    <div class="row-meta">{short_text(row.get("description", ""), 120)}</div>
                </div>
                """, unsafe_allow_html=True)

                with st.expander(f"📖 {row.get('structure_name', '')} detaylarını aç"):
                    st.write(f"**Yapı adı:** {row.get('structure_name', '')}")
                    st.write(f"**Yapı türü:** {row.get('structure_type', '')}")
                    st.write(f"**İl / İlçe:** {row.get('city', '')} / {row.get('district', '')}")
                    st.write(f"**Adres:** {row.get('address', '')}")
                    st.write(f"**Koordinat:** {row.get('latitude', '')}, {row.get('longitude', '')}")
                    st.write(f"**Korunma durumu:** {row.get('condition_status', '')}")
                    st.write(f"**Ekleyen:** @{row.get('added_by', 'Belirtilmemiş')}")

                    st.markdown("### Metin Bilgisi / Açıklama")
                    st.write(row.get("description", "Açıklama eklenmemiş."))

                    st.link_button(
                        "📍 Google Maps’te Aç",
                        google_maps_link(row.get("latitude"), row.get("longitude"))
                    )

                    if related_photos:
                        st.markdown("### Fotoğraflar")
                        cols = st.columns(3)
                        for i, p in enumerate(related_photos):
                            with cols[i % 3]:
                                st.image(
                                    p.get("photo_url"),
                                    caption=p.get("structure_name") or p.get("caption"),
                                    use_container_width=True
                                )
                    else:
                        st.info("Bu yapı için fotoğraf bulunamadı.")

                    st.markdown("""
                    <div class="delete-box">
                    Yanlış eklenen kayıtları buradan silebilirsin.
                    </div>
                    """, unsafe_allow_html=True)

                    if st.button(
                        f"🗑️ {row.get('structure_name', '')} kaydını sil",
                        key=f"delete_{row.get('id')}"
                    ):
                        try:
                            delete_structure(row.get("id"))
                            st.success("Kayıt silindi.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Silme sırasında hata oluştu: {e}")

    elif menu == "Harita":
        st.subheader("🗺️ Harita")

        if not structures:
            st.info("Haritada gösterilecek kayıt yok.")
        else:
            df = pd.DataFrame(structures)

            m = folium.Map(
                location=[df["latitude"].mean(), df["longitude"].mean()],
                zoom_start=11,
                tiles="CartoDB positron"
            )

            for _, row in df.iterrows():
                popup_text = f"""
                <b>{row.get('structure_name')}</b><br>
                Tür: {row.get('structure_type')}<br>
                Konum: {row.get('city')} / {row.get('district')}<br>
                Ekleyen: {row.get('added_by', 'Belirtilmemiş')}<br>
                <a href="{google_maps_link(row.get('latitude'), row.get('longitude'))}" target="_blank">
                Google Maps’te Aç
                </a>
                """

                folium.Marker(
                    location=[row.get("latitude"), row.get("longitude")],
                    popup=popup_text,
                    tooltip=row.get("structure_name"),
                    icon=folium.Icon(icon="tint", prefix="fa", color="blue")
                ).add_to(m)

            st_folium(m, width=900, height=540)

    elif menu == "Galeri":
        st.subheader("🖼️ Galeri")

        if not photos:
            st.info("Henüz fotoğraf yok.")
        else:
            cols = st.columns(3)

            for i, p in enumerate(photos):
                with cols[i % 3]:
                    st.image(
                        p.get("photo_url"),
                        caption=p.get("structure_name") or p.get("caption"),
                        use_container_width=True
                    )


with right_col:
    st.markdown("<div class='stream-title'>🎞️ Fotoğraf akışı</div>", unsafe_allow_html=True)

    count = st_autorefresh(interval=4000, key="slideshow_refresh")

    if not photos:
        st.markdown("""
        <div class="note-box">
        Fotoğraf yüklendiğinde burada otomatik görsel akış oluşur.
        </div>
        """, unsafe_allow_html=True)
    else:
        index = count % len(photos)
        selected = photos[index]

        st.image(
            selected.get("photo_url"),
            caption=selected.get("structure_name") or selected.get("caption"),
            use_container_width=True
        )

    st.markdown("""
    <div class="tiny-note">
    Kayıtlar ve fotoğraflar Supabase üzerinde kalıcıdır.
    </div>
    """, unsafe_allow_html=True)
!wget -q -O cloudflared https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64
!chmod +x cloudflared

!streamlit run app.py --server.port 8501 &>/content/logs.txt &

!./cloudflared tunnel --url http://localhost:8501 

