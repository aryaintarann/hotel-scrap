# PRD — HotelPilot (nama kerja)

> Agen AI headless yang mengumpulkan data hotel, menganalisisnya, menulis konten blog (ID + EN) beserta aset gambar, lalu menerbitkan dan membagikannya otomatis ke Threads setiap 2 jam.
> Versi 0.3 · 18 Nov 2026 · Pemilik: Arya (Teridox)
> **Lingkup assessment v0.3**: tabel "Keputusan v0.2–v0.3" di `TASKS.md` menimpa dokumen ini bila bertentangan.

---

## 1. Tujuan

| # | Tujuan | Ukuran sukses |
|---|--------|---------------|
| G1 | Mengumpulkan data hotel Bali dari sumber legal secara berkala | ≥ 200 hotel ternormalisasi (nama, koordinat, ≥ 3 atribut) di bulan pertama |
| G2 | Menghasilkan artikel blog bilingual (ID + EN) yang berbasis data nyata | 100% klaim faktual terpetakan ke data sumber |
| G3 | Menghasilkan aset visual (prompt gambar + alt text) per artikel | 1 hero + 2 gambar pendukung per artikel |
| G4 | Memublikasikan dan berbagi otomatis tanpa intervensi manual | 12 posting Threads/hari, ≥ 99% sukses, deviasi waktu ≤ 5 menit |
| G5 | Bisa dipasang ke frontend apa pun (Next.js, Nuxt, Astro, Laravel, dll.) | Cukup lewat REST API, feed, dan webhook |

## 2. Keputusan yang Sudah Dikunci

| Topik | Keputusan |
|-------|-----------|
| Sumber data | **Data terbuka**: Overture Maps Places (CDLA-Permissive-2.0/Apache-2.0) sebagai sumber utama, OpenStreetMap via Overpass (ODbL) untuk atribut tambahan. Google Places dibatalkan (v0.3). Crawl web masuk roadmap |
| Platform sosial | **Threads** (Meta Threads API) |
| Tech stack | **Python (FastAPI) + Supabase** (Postgres, Storage, Auth) |
| Niche dan bahasa | **Bali**, **bilingual ID + EN** |
| Gambar | Sistem menghasilkan **prompt gambar + alt text + brief**. Generasi gambar otomatis bersifat opsional lewat adapter (Fase lanjutan) |
| Frekuensi | Setiap 2 jam, 12 slot/hari, zona waktu Asia/Makassar (WITA) |

**Catatan sumber data (hasil verifikasi per Nov 2026)**
- Expedia dan Kayak **tidak dipakai sebagai target scraping langsung**: ToS melarang dan anti-bot agresif membuat pipeline rapuh.
- Portal Amadeus Self-Service **sudah ditutup 17 Juli 2026**, jadi tidak masuk rencana.
- Google Places API **dibatalkan** (v0.3): SKU Enterprise untuk rating berbayar, dan ToS hanya mengizinkan penyimpanan `place_id` permanen dan koordinat ≤ 30 hari.
- Sumber MVP: **Overture Maps Places** (diunduh sekali via DuckDB, filter `taxonomy` lodging + bbox Bali) dan **OpenStreetMap/Overpass** (`tourism=hotel/guest_house/hostel/resort`: bintang, amenitas, website). TripAdvisor dan crawl web masuk roadmap.
- **Tidak ada rating tamu** di MVP. Analisis memakai kelengkapan dan kualitas atribut.
- Data **harga real-time** tidak tersedia dari sumber di atas. Insight harga di MVP dibatasi ke rentang bintang. Harga aktual masuk Fase lanjutan lewat API partner/afiliasi.

## 3. Pengguna

| Persona | Kebutuhan |
|---------|-----------|
| **Operator** (Arya/tim Teridox) | Mengatur wilayah, jadwal, tone, melihat antrean, menyetujui atau menolak konten, menerima alert bila gagal |
| **Pengembang frontend** | Mengambil artikel lewat API/feed dan merender di framework apa pun |
| **Pembaca akhir** | Wisatawan yang mencari rekomendasi hotel Bali yang jujur dan terkini |

## 4. Ruang Lingkup

**Dalam lingkup (MVP)**
- Ingestion hotel Bali dari 2 sumber terbuka (Overture, OSM), normalisasi, dedupe, snapshot per sapuan
- Analisis: ranking per area, perbandingan area, segmentasi (keluarga, pasangan, budget, mewah), deteksi perubahan atribut
- Perencana topik otomatis
- Penulisan artikel ID + EN, meta SEO, FAQ, alt text, prompt gambar, snippet sosial
- QA otomatis (grounding, duplikasi, kebijakan)
- Penjadwalan dan publikasi blog (API + webhook revalidate) dan Threads tiap 2 jam
- Dashboard operator minimal (antrean, log, approve/reject)
- Alert kegagalan (Discord/Telegram)

**Di luar lingkup (MVP)**
- Generasi gambar otomatis, video, platform sosial lain (Instagram, Facebook, X)
- Booking, pembayaran, harga real-time
- UI blog publik (disediakan frontend masing-masing)

## 5. Kebutuhan Fungsional

Prioritas: **P0** wajib MVP · **P1** penting · **P2** nanti.

### 5.1 Ingestion
| ID | Kebutuhan | Prio |
|----|-----------|------|
| FR-01 | Provider data berbentuk plugin (satu antarmuka, banyak sumber) | P0 |
| FR-02 | Konfigurasi wilayah (Bali dan sub-area: Ubud, Canggu, Seminyak, Nusa Dua, dst.) | P0 |
| FR-03 | Normalisasi ke skema hotel seragam (nama, alamat, koordinat, bintang, amenitas, kategori, kontak, confidence sumber) | P0 |
| FR-04 | Dedupe lintas sumber (nama fuzzy + jarak koordinat) | P0 |
| FR-05 | Simpan snapshot mentah dan ternormalisasi dengan `source` + `fetched_at`, agar perubahan atribut antar-sapuan bisa dideteksi | P0 |
| FR-06 | Patuhi robots.txt, rate limit per domain, dan batas cache tiap provider | P0 |
| FR-07 | Sapuan terjadwal 1× per bulan per sumber, dengan cache (Overpass < 100 query/hari, jeda antar request) | P1 |
| FR-08 | Dukungan wilayah lain tanpa ubah kode (konfigurasi saja) | P2 |

### 5.2 Analisis
| ID | Kebutuhan | Prio |
|----|-----------|------|
| FR-10 | Hitung skor kelengkapan & kualitas atribut per hotel (bintang, jumlah fasilitas, kelengkapan kontak, confidence Overture) | P0 |
| FR-11 | Hasilkan insight terstruktur (top-N per area/segmen, perbandingan area, perubahan atribut sejak sapuan sebelumnya) | P0 |
| FR-12 | Perencana topik: pilih topik berikutnya, hindari topik yang baru dibuat | P0 |
| FR-13 | Setiap insight menyimpan referensi hotel dan field sumber (untuk grounding) | P0 |

### 5.3 Generasi Konten
| ID | Kebutuhan | Prio |
|----|-----------|------|
| FR-20 | Artikel blog lengkap: judul, slug, ringkasan, isi Markdown, FAQ, meta title/description | P0 |
| FR-21 | Versi ID dan EN dihasilkan sebagai satu paket (bukan terjemahan mentah, tetapi adaptasi) | P0 |
| FR-22 | Per artikel: 1 hero + 2 gambar pendukung berupa prompt, alt text, rasio, gaya | P0 |
| FR-23 | Snippet Threads (≤ 500 karakter, 1 topic tag) minimal 6 variasi sudut pandang per artikel | P0 |
| FR-24 | Tone dan gaya merek bisa diatur (style guide di konfigurasi) | P1 |
| FR-25 | Adapter generasi gambar opsional (provider pluggable) | P2 |

### 5.4 Kualitas dan Kebijakan
| ID | Kebutuhan | Prio |
|----|-----------|------|
| FR-30 | Grounding check: angka dan klaim di artikel harus ada di data sumber, jika tidak artikel ditolak | P0 |
| FR-31 | Deteksi duplikasi/kemiripan dengan konten lama (embedding) | P0 |
| FR-32 | Larangan menyalin teks ulasan atau deskripsi sumber secara verbatim | P0 |
| FR-33 | Label transparansi: konten dibantu AI + tanggal data diambil | P0 |
| FR-34 | Mode review manual (konten tertahan sampai disetujui), bisa diaktifkan per jenis konten | P1 |

### 5.5 Publikasi dan Distribusi
| ID | Kebutuhan | Prio |
|----|-----------|------|
| FR-40 | Publikasi blog lewat REST API, feed JSON, RSS, sitemap | P0 |
| FR-41 | Webhook ke frontend setelah publish (revalidate/rebuild) | P0 |
| FR-42 | Penjadwal: 1 posting Threads tiap 2 jam, 12 slot/hari WITA | P0 |
| FR-43 | Antrean dengan idempotensi, retry eksponensial, dead-letter setelah 3 gagal | P0 |
| FR-44 | Alur publish Threads dua langkah (buat container, cek status, publish) | P0 |
| FR-45 | Pantau kuota (`threads_publishing_limit`) dan refresh token otomatis sebelum kedaluwarsa | P0 |
| FR-46 | Buffer konten: sistem menjaga minimal 24 posting siap tayang (48 jam), fallback ke konten evergreen bila habis | P1 |
| FR-47 | Variasi posting (hindari pola spam): rotasi sudut, jam, format teks/gambar | P1 |
| FR-48 | Adapter kanal baru (Instagram, Facebook, X, Telegram) tanpa ubah inti | P2 |

### 5.6 Operasi
| ID | Kebutuhan | Prio |
|----|-----------|------|
| FR-50 | Dashboard operator: antrean, status job, log, approve/reject, pause semua | P1 |
| FR-51 | Alert ke Discord/Telegram saat job gagal, token hampir habis, atau buffer menipis | P0 |
| FR-52 | Laporan harian ringkas (posting terkirim, gagal, biaya LLM) | P1 |
| FR-53 | Tombol kill-switch global untuk menghentikan semua publikasi | P0 |

## 6. Kebutuhan Non-Fungsional

| ID | Kebutuhan |
|----|-----------|
| NFR-01 | **Keandalan**: ≥ 99% slot 2 jam terisi dan terkirim, deviasi ≤ 5 menit |
| NFR-02 | **Idempotensi**: job yang diulang tidak membuat posting ganda |
| NFR-03 | **Keamanan**: token sosial terenkripsi di database, rahasia di env, RLS aktif di Supabase, API admin butuh autentikasi |
| NFR-04 | **Observabilitas**: log terstruktur, ID korelasi per run, metrik biaya LLM per artikel |
| NFR-05 | **Biaya**: target awal ≤ US$0,30 per artikel dua bahasa (diukur ulang di Fase 3) |
| NFR-06 | **Portabilitas**: API terdokumentasi OpenAPI, dapat dibuatkan klien TypeScript otomatis |
| NFR-07 | **Testabilitas**: provider dan LLM dapat di-mock, ada fixture data hotel |
| NFR-08 | **Kepatuhan**: patuh ToS tiap provider, aturan Meta Platform, dan batas cache data |

## 7. Risiko

| Risiko | Dampak | Mitigasi |
|--------|--------|----------|
| Halusinasi AI (fakta hotel salah) | Reputasi dan kepercayaan | Grounding check wajib, penulis hanya boleh memakai fakta dari paket data (`facts`), mode review manual |
| Scraping diblokir atau melanggar ToS | Pipeline berhenti, risiko hukum | API resmi sebagai prioritas, crawl hanya situs yang mengizinkan, provider terisolasi |
| Lisensi data terbuka (ODbL OSM, CDLA Overture) | Pelanggaran lisensi | Atribusi "© OpenStreetMap contributors" + Overture di footer blog dan field `attribution` API; data per sumber disimpan terpisah; endpoint data hotel gabungan diberi label ODbL |
| Data terbuka kurang lengkap (tanpa rating, atribut jarang) | Konten tipis | Target diturunkan ke ≥ 200 hotel dengan ≥ 3 atribut; skor kelengkapan; angka nyata dilaporkan setelah ingest |
| Akun Threads dinilai spam (12 posting/hari, pola seragam) | Pembatasan akun | Variasi konten dan jam, nilai tambah nyata per posting, kontrol kuota |
| Token Threads kedaluwarsa (60 hari) | Publikasi berhenti diam-diam | Job refresh otomatis, alert saat sisa < 15 hari |
| Biaya LLM membengkak | Anggaran | Model berjenjang (model murah untuk klasifikasi, model kuat untuk penulisan), cache hasil analisis, batas anggaran harian |
| Duplikasi konten antar-artikel (SEO) | Peringkat turun | Embedding similarity dan perencana topik |

## 8. Metrik

- Ketepatan jadwal: persentase posting terkirim dalam ±5 menit
- Tingkat kelulusan QA pada percobaan pertama
- Rasio klaim terpetakan ke sumber (target 100%)
- Biaya LLM per artikel dan per posting
- Trafik referral Threads ke blog, engagement per posting (diukur mulai Fase 6)

## 9. Milestone

| Fase | Isi | Hasil |
|------|-----|-------|
| M0 | Fondasi repo, spec, skema DB | Repo siap, CI hijau |
| M1 | Ingestion + normalisasi | Dataset hotel Bali di DB |
| M2 | Analisis + perencana topik | Insight terstruktur |
| M3 | Generator konten + QA | Artikel ID/EN + prompt gambar lolos QA |
| M4 | Publikasi blog + feed + webhook | Frontend demo menampilkan artikel |
| M5 | Penjadwal + Threads | Posting otomatis tiap 2 jam |
| M6 | Dashboard, alert, hardening | Siap produksi |

Rincian ada di `TASKS.md`, desain teknis di `ARCHITECTURE.md`.

## 10. Pendekatan Pengembangan: Spec-Driven + Vibe Coding

1. **Spec dulu**: tiap fitur punya berkas di `specs/NNN-nama.md` (tujuan, kontrak I/O, kriteria penerimaan, kasus tepi).
2. **Vibe coding terarah**: AI menulis kode dari spec, bukan dari ide mentah. Konteks tetap ada di `CLAUDE.md` (aturan repo) dan `specs/`.
3. **Tes sebagai gerbang**: kriteria penerimaan diubah jadi tes sebelum/bersama implementasi. Tugas selesai hanya bila tes lulus.
4. **Iterasi kecil**: satu tugas, satu spec, satu PR/commit.
5. **Spec adalah sumber kebenaran**: bila perilaku berubah, spec diubah lebih dulu.

## 11. Asumsi dan Pertanyaan Terbuka

**Asumsi**
- Akun Threads (via Instagram) sudah ada dan Meta App dibuat dengan akun sendiri sebagai tester.
- Frontend blog dibuat terpisah dan menerima konten lewat API/webhook.
- Tidak ada API berbayar untuk data hotel; DuckDB dapat membaca S3 publik Overture dari VPS/lokal.
- Hosting agen: Docker di VPS milik sendiri, database di Supabase.

**Perlu diputuskan sebelum M3**
1. Mode review awal: otomatis penuh atau 2 minggu pertama wajib approve manual? (disarankan manual dulu)
2. Apakah artikel memuat tautan afiliasi? (memengaruhi kewajiban disclosure)
3. Domain dan frontend blog target untuk demo integrasi.
4. Batas anggaran LLM bulanan.
