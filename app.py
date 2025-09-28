# 1. Impor library yang dibutuhin
from flask import (
    Flask,
    request,
    jsonify,
)  # Flask core + akses data request + respon JSON
import os  # akses environment variable
from dotenv import load_dotenv  # buat load file .env
import google.generativeai as genai  # library Gemini (google-generativeai)
import base64
import json
import random

# 2. Load variabel dari file .env (kalo ada). Letakkan sedini mungkin.
load_dotenv()

# 3. Konfigurasi Gemini API pakai API key dari environment variable GEMINI_API_KEY
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    # Simple guard biar gampang notice kalo lupa set key.
    raise RuntimeError(
        "Environment variable GEMINI_API_KEY belum diset. Isi dulu di .env atau sistem env."
    )
genai.configure(api_key=api_key)

# 4. Bikin aplikasi server kita dari cetakan itu (instance Flask)
app = Flask(__name__)


# 5. Bikin alamat URL pertama kita
# @app.route('/') artinya "Kalo ada yang akses alamat utama (root)"
@app.route("/")
def home():
    # "maka jalankan fungsi ini dan kirim jawaban ini"
    return "Halo, servernya nyala!"


# 6-15. Endpoint buat analisa gambar pakai Gemini
@app.route("/analyze", methods=["POST"])
def analyze_image():
    # Ganti dari request.files jadi request.form
    image_data = request.form.get("image")

    if not image_data:
        return jsonify({"error": "Tidak ada gambar yang dikirim"}), 400

    try:
        # Decode Base64 jadi bytes
        gambar_bytes = base64.b64decode(image_data)

        # Kita nggak tau mimetype-nya, jadi hardcode aja
        mime_type = "image/jpeg"

        model = genai.GenerativeModel("gemini-2.5-flash")
        prompt_parts = [
            """
            Analisis gambar ini. Fokus HANYA pada objek utama yang paling menonjol di tengah gambar, yang diletakkan di atas sebuah pola. Abaikan pola kotak-kotak di bawahnya dan abaikan latar belakang.
            Berikan jawaban dalam format berikut, tanpa basa-basi:
            
            Penjelasan: [deskripsi singkat objek dalam 1-2 kalimat]
            Fungsi: [fungsi utama objek]
            Fakta Unik: [satu fakta menarik tentang objek ini]
            """,
            {
                "mime_type": mime_type,
                "data": gambar_bytes,
            },
        ]
        response = model.generate_content(prompt_parts)
        hasil_teks = getattr(response, "text", None)
        if not hasil_teks:
            try:
                hasil_teks = response.candidates[0].content.parts[0].text
            except Exception:
                hasil_teks = "(Tidak ada deskripsi yang bisa diambil)"
        return jsonify({"description": hasil_teks})
    except Exception as e:
        return jsonify({"error": f"Gagal analisa: {str(e)}"}), 500


@app.route("/generate-quiz", methods=["POST"])
def generate_quiz():
    # 1. Ambil data yang dikirim dari Unity
    deskripsi = request.form.get("description_text")
    # Ambil daftar soal sebelumnya. Default-nya string kosong kalo ga dikirim.
    previous_questions_json = request.form.get("previous_questions", "[]")

    # 2. Cek kalau-kalau data deskripsi kosong
    if not deskripsi:
        return jsonify({"error": "Tidak ada teks deskripsi yang dikirim"}), 400

    try:
        # 3. Ubah JSON string dari Unity jadi list Python
        previous_questions = json.loads(previous_questions_json)

        # 4. Siapkan bagian prompt untuk soal-soal sebelumnya
        history_prompt_part = ""
        if previous_questions:  # Kalo list-nya nggak kosong
            # Gabungkan semua soal sebelumnya jadi satu blok teks
            questions_text = "\n".join(f"- {q}" for q in previous_questions)
            history_prompt_part = f"""
            PENTING: Jangan membuat pertanyaan yang mirip atau sama dengan pertanyaan di daftar berikut:
            {questions_text}
            """
        model = genai.GenerativeModel("gemini-2.5-flash")

        prompt = f"""
            Kamu adalah seorang guru yang membuat soal kuis untuk anak-anak usia 8-10 tahun.
            Berdasarkan teks informasi berikut:
            "{deskripsi}"

            Tugasmu:
            1. Buat SATU pertanyaan yang SINGKAT dan MUDAH DIPAHAMI dari informasi paling penting di teks itu.
            2. Buat 4 pilihan jawaban yang juga SANGAT SINGKAT (maksimal 4 kata per pilihan).
            3. Pastikan hanya ada satu jawaban yang benar.
            4. Pastikan pilihan jawaban pengecohnya sederhana dan tidak membingungkan.

            {history_prompt_part}

            Berikan hasilnya HANYA dalam format JSON yang ketat seperti ini, tanpa tambahan teks atau penjelasan apapun:
            {{
            "question": "Isi pertanyaan singkat di sini",
            "options": [
                "Jawaban singkat A",
                "Jawaban singkat B",
                "Jawaban singkat C",
                "Jawaban singkat D"
            ],
            "correct_answer_index": Angka_indeks_jawaban_yang_benar
            }}
            """

        # 23. Kirim resep ke Gemini
        response = model.generate_content(prompt)

        # 24. Ambil "masakan jadi" dan bersihkan
        hasil_json_mentah = (
            response.text.strip().replace("```json", "").replace("```", "")
        )

        # 25. Ubah string JSON mentah menjadi objek Python (dictionary)
        data_kuis = json.loads(hasil_json_mentah)

        # --- INI DIA MESIN PENGOCOKNYA ---
        # 26. Ambil daftar pilihan jawaban dan jawaban yang benar
        pilihan_jawaban = data_kuis["options"]
        jawaban_benar_teks = pilihan_jawaban[data_kuis["correct_answer_index"]]

        # 27. Acak urutan pilihan jawaban
        random.shuffle(pilihan_jawaban)

        # 28. Cari di mana posisi BARU si jawaban yang benar setelah diacak
        indeks_baru_jawaban_benar = pilihan_jawaban.index(jawaban_benar_teks)
        # --- SELESAI MENGOCok ---

        # 29. Update data kuis dengan urutan yang sudah diacak dan indeks yang baru
        data_kuis_teracak = {
            "question": data_kuis["question"],
            "options": pilihan_jawaban,  # Ini list yang sudah diacak
            "correct_answer_index": indeks_baru_jawaban_benar,  # Ini indeks baru yang benar
        }

        # 30. Kembalikan data yang sudah diacak ini sebagai JSON ke Unity
        return jsonify(data_kuis_teracak)

    except Exception as e:
        # 31. Kalau ada error
        return jsonify({"error": f"Gagal membuat kuis: {str(e)}"}), 500


# 16-17. Blok standar run Flask
if __name__ == "__main__":
    # Jalanin di host 0.0.0.0 port 5000 dengan debug nyala
    app.run(host="0.0.0.0", port=5000, debug=True)
