# TASKS — HotelPilot (nama kerja)

> Versi 0.3 · 18 Nov 2026 · Turunan dari `PRD.md` dan `ARCHITECTURE.md`.
> Ukuran: **S** ≤ 0,5 hari · **M** 1–2 hari · **L** 3+ hari.
> **Lingkup v0.2: irisan tipis end-to-end untuk technical assessment.** Task di luar irisan dipindah ke bagian *Roadmap* (juga dicatat di `README.md`).

---

## Irisan Tipis (target assessment)

```
Overture Places + OSM (Overpass) → normalisasi/dedupe → skor kelengkapan + insight → Fact Pack
→ 1 artikel ID+EN (+ prompt gambar + snippet) → QA dasar → publish blog (API)
→ Threads TEXT tiap 2 jam (WITA)
```

## Keputusan v0.2–v0.3 (mengikat, menimpa PRD/ARCH bila bertentangan)

| Ver | Topik | Keputusan |
|-----|-------|-----------|
| v0.3 | Google Places | **Dibatalkan** (biaya SKU Enterprise + ToS melarang menyimpan nama/rating). Spike S-2 Places dihapus. |
| v0.3 | Sumber utama | **Overture Maps Places** (CDLA-Permissive-2.0 / Apache-2.0): unduh sekali via DuckDB dari rilis terbaru (katalog STAC), filter `taxonomy.hierarchy` berisi `lodging` + bbox Bali. Field `categories` sudah dihapus Overture sejak rilis Sep 2026, jangan dipakai. |
| v0.3 | Sumber atribut | **OSM via Overpass** (`tourism=hotel/guest_house/hostel/resort`): `stars`, amenitas, `website`. Wajib cache, < 100 query/hari, jeda antar request, tanpa query paralel, 1 sapuan per bulan, User-Agent jujur, 429 → jeda ≥ 30 dtk. |
| v0.3 | Penyimpanan sumber | Tiap record mentah menyimpan `source` + `fetched_at`; data OSM dan Overture disimpan terpisah per sumber, `hotels` hanya menautkan. |
| v0.3 | Dedupe | Nama fuzzy + jarak koordinat, ditambah kecocokan domain `website` bila ada. |
| v0.3 | Rating | **Tidak ada rating tamu.** Skor komposit diganti **skor kelengkapan & kualitas atribut**: bintang, jumlah fasilitas, kelengkapan kontak, `confidence` Overture. |
| v0.3 | Perubahan data | FR-05/FR-11 menjadi **deteksi perubahan atribut** antar-sapuan (bintang, fasilitas, kontak, status operasi). |
| v0.3 | Target dataset | T-017: **≥ 200 hotel** dengan nama, koordinat, dan ≥ 3 atribut; angka nyata dilaporkan setelah ingest. |
| v0.3 | Atribusi | Footer blog: "© OpenStreetMap contributors" (ODbL) dan "Overture Maps Foundation". API menyertakan field `attribution`. Endpoint data hotel gabungan diberi label ODbL. |
| v0.2 | Format posting | **Hanya TEXT** di MVP. Prompt gambar + alt text tetap dihasilkan dan disimpan di artikel. |
| v0.2 | Kemiripan konten | **Tanpa penyedia embedding.** `pg_trgm` untuk kemiripan judul + rotasi area/kategori di perencana topik. |
| v0.2 | Slot terlewat | Telat ≤ 30 menit → tetap post. Telat > 30 menit → skip + log. **Tidak ada catch-up beruntun.** |
| v0.2 | Urutan publikasi | Snippet hanya boleh `queued` setelah artikelnya `published`. |
| v0.2 | Slug | Satu slug per artikel, URL `/id/{slug}` dan `/en/{slug}`. |
| v0.2 | Label AI | Label AI + `data_as_of` di blog. Snippet cukup hashtag pendek (mis. `#AIassisted`) agar hemat karakter. |
| v0.2 | Mode review | Dimatikan untuk demo. Artikel gagal QA **tidak pernah** diposting. |
| v0.2 | Webhook | Kirim sekali, tanpa retry (retry masuk roadmap). |

---

## 0. Cara Kerja (Spec-Driven + Vibe Coding)

**Siklus tiap tugas**
1. Buka/buat `specs/NNN-*.md` (tujuan, kontrak I/O, kriteria penerimaan, kasus tepi).
2. Tulis **tes dari kriteria penerimaan** terlebih dahulu.
3. Implementasikan sampai tes lulus.
4. Jalankan `ruff`, `mypy`, `pytest`. Review diff, lalu commit kecil.
5. Centang tugas di berkas ini. Bila perilaku berubah, ubah spec dulu.

**Definisi Selesai (DoD)**: kriteria penerimaan terpenuhi · tes lulus · lint dan tipe bersih · spec sinkron · tidak ada rahasia di repo · log dan error path teruji.

---

## Fase 0 — Fondasi + Spike Risiko (M0)

- [x] **T-001 · Inisialisasi repo** (S)
  Struktur folder sesuai ARCHITECTURE §12, `pyproject.toml` (uv), ruff, mypy, pytest, `Makefile`, `CLAUDE.md`, `.env.example`, `README.md` (berisi roadmap).
  *Terima*: `make test` dan `make lint` jalan hijau.
- [ ] **T-002 · CI GitHub Actions** (S) · dep: T-001
  *Terima*: PR menjalankan lint, mypy, pytest otomatis.
- [x] **T-005 · Docker Compose lokal** (S) · dep: T-001
  `api` dan `worker`, healthcheck.
  *Terima*: `docker compose up` menampilkan `/healthz` OK.
- [ ] **S-1 · Spike Threads** 🔴 (S) · dep: T-001
  Token jangka panjang dari akun uji, cek scope (`threads_basic`, `threads_content_publish`), satu posting TEXT lewat container → status → publish, baca `threads_publishing_limit`.
  *Terima*: satu posting terbit di akun uji; laporan token, scope, kuota, dan ToS dikirim ke pemilik sebelum lanjut.
- [x] ~~**S-2 · Spike Google Places (New)**~~ — dibatalkan di v0.3 (hasil riset: SKU Enterprise + ToS cache). Digantikan T-011 Overture.
- [x] **T-003 · Spec 001 skema DB + migrasi + RLS** (M) · dep: T-001
  Tabel sesuai ARCHITECTURE §6 (tanpa kolom `embedding`, tanpa rating), ekstensi `pg_trgm`, RLS, seed `regions` (Bali + sub-area), `sources` (overture, osm) dan `settings`.
  *Terima*: `supabase db reset` berjalan bersih di Supabase lokal; tes RLS lulus (anon tidak bisa baca tabel internal).
- [x] **T-004 · Config, logging, klien DB, klien LLM** (M) · dep: T-001
  Pydantic Settings, `structlog` dengan `run_id`, pembungkus Claude API (retry, hitung token dan biaya ke `run_logs`).
  *Terima*: panggilan LLM ter-mock tercatat biayanya; env wajib divalidasi saat start.
- [ ] **T-037 · Anggaran LLM harian** (S) · dep: T-004
  *Terima*: melewati batas menghentikan generasi, tidak mematikan publikasi dari buffer.
- [x] **T-060 · Spec 011 notifier Discord/Telegram** (S) · dep: T-004 *(dimajukan: dipakai T-052, T-054, T-055)*
  *Terima*: job dead, token hampir habis, buffer rendah, anggaran > 80% mengirim alert; tanpa webhook URL → hanya log.

## Fase 1 — Antrean, Threads, Scheduler Dummy, Deploy Awal

- [ ] **T-050 · Spec 009 antrean `jobs` + worker** 🟡 (M) · dep: T-003
  `SKIP LOCKED`, retry eksponensial (1 → 5 → 15 mnt), dead-letter, `idempotency_key` unik.
  *Terima*: tes konkurensi dua worker tidak memproses job yang sama; job yang diulang tidak ganda.
- [ ] **T-051 · Spec 010 channel Threads (TEXT)** 🔴 (M) · dep: T-050, S-1
  Alur container → cek status → publish, validasi 500 karakter (byte-aware untuk emoji), kuota `threads_publishing_limit`, token terenkripsi di `social_accounts`.
  *Terima*: kontrak diuji dengan respons ter-mock; satu posting ke akun uji berhasil.
- [ ] **T-052 · Refresh token otomatis + alert** 🟡 (S) · dep: T-051, T-060
  *Terima*: token dengan sisa < 15 hari di-refresh; kegagalan memicu alert.
- [ ] **T-054 · Scheduler slot 2 jam (WITA) + pemilih konten** 🔴 (M) · dep: T-050, T-051, T-060
  12 slot/hari, tick tiap menit, hormati `kill_switch`. Aturan variasi: bukan sudut sama dengan 3 posting terakhir, bukan artikel sama berturut-turut. Hanya pilih snippet yang artikelnya `published`. Slot telat ≤ 30 mnt → post; > 30 mnt → skip + log; tanpa catch-up beruntun.
  *Terima*: simulasi waktu 48 jam menghasilkan 24 slot terisi tanpa duplikasi; simulasi downtime 3 jam menghasilkan skip ter-log dan tidak ada posting beruntun saat pulih; snippet dari artikel belum terbit tidak pernah dipilih. Awalnya diuji dengan posting dummy.
- [ ] **T-064 · Deploy awal ke VPS** (M) · dep: T-005, T-054 *(dimajukan: segera setelah scheduler dummy berjalan)*
  Docker Compose produksi, env dari secret, rotasi log, runbook singkat (token, kill-switch).
  *Terima*: worker di VPS memposting dummy ke akun uji sesuai slot selama ≥ 6 jam.

## Fase 2 — Ingestion & Normalisasi

- [ ] **T-010 · Spec 002 antarmuka `HotelProvider` + runner** (M) · dep: T-003, T-004
  Runner per wilayah, paginasi, rate limit, simpan `raw_snapshots` dengan `fetched_at`/`expires_at`.
  *Terima*: provider dummy menghasilkan snapshot; kegagalan satu provider tidak menghentikan lainnya.
- [ ] **T-011 · Provider Overture Places (DuckDB)** 🟡 (M) · dep: T-010
  Rilis terbaru dari katalog STAC, `read_parquet` S3 dengan filter bbox Bali + `'lodging' = ANY(taxonomy.hierarchy)`; ambil nama, koordinat, `basic_category`, `taxonomy`, `confidence`, `operating_status`, websites, phones, emails, socials, alamat. Unduhan disimpan lokal sebagai cache Parquet; sapuan ulang hanya bila rilis berganti dan ≥ 30 hari.
  *Terima*: fixture Parquet kecil ter-parse ke `NormalizedHotel`; tiap record punya `source='overture'`, `fetched_at`, versi rilis.
- [ ] **T-012 · Provider OpenStreetMap (Overpass)** 🟡 (S) · dep: T-010
  `tourism=hotel|guest_house|hostel|resort` per sub-area bbox: `stars`, amenitas (`internet_access`, `swimming_pool`, `wheelchair`, dll.), `website`, `phone`. Cache respons per query; < 100 query/hari; jeda ≥ 5 dtk antar request; tanpa paralel; 429/504 → jeda ≥ 30 dtk lalu coba lagi maks. 3×; 1 sapuan per bulan.
  *Terima*: fixture respons nyata terpetakan; tes membuktikan cache dipakai (tanpa HTTP kedua) dan pembatas kuota harian menolak query ke-100.
- [ ] **T-015 · Spec 003 Normalizer + Dedupe** (M) · dep: T-011, T-012
  Nama fuzzy + jarak ≤ ambang (+ domain `website` sama → cocok kuat), simpan `merged_from` (ID per sumber).
  *Terima*: set uji dengan duplikat sengaja menghasilkan satu hotel; presisi dedupe ≥ 95% pada set uji.
- [ ] **T-017 · Seed dataset Bali** (S) · dep: T-015
  *Terima*: ≥ 200 hotel di `hotels` dengan nama, koordinat, dan ≥ 3 atribut; laporan angka nyata (total, per sumber, per area, sebaran atribut).
- [ ] **T-016 · Sapuan bulanan + deteksi perubahan atribut** (S) · dep: T-015, T-050 *(dipindah: butuh antrean)*
  *Terima*: sapuan kedua mencatat perubahan atribut (bintang, fasilitas, kontak, status operasi) ke `hotel_snapshots`; tercatat di log.

## Fase 3 — Analisis & Perencana Topik

- [ ] **T-020 · Spec 004 skor kelengkapan & kualitas atribut** (S) · dep: T-017
  Komponen: bintang (OSM), jumlah fasilitas, kelengkapan kontak (website/telepon/email), `confidence` Overture; bobot di spec.
  *Terima*: tes properti (menambah atribut tidak pernah menurunkan skor; `operating_status` tutup → skor 0).
- [ ] **T-021 · Insight engine** (M) · dep: T-020
  Top-N per area/segmen (berdasar skor kelengkapan + fasilitas), perbandingan dua area (jumlah, sebaran bintang, fasilitas); tulis `insights` + `insight_refs`. Perubahan atribut menyusul setelah ada ≥ 2 sapuan.
  *Terima*: tiap angka dalam `result` punya `insight_refs`.
- [ ] **T-022 · Spec 005 Topic Planner** (M) · dep: T-021, T-003
  Rotasi area/kategori + `pg_trgm` `similarity()` terhadap judul/topik terbaru.
  *Terima*: 20 topik berturut-turut tanpa pasangan dengan similarity di atas ambang dan tanpa area sama beruntun.

## Fase 4 — Generator Konten & QA

- [ ] **T-030 · Spec 006 Fact Pack builder** (M) · dep: T-021
  *Terima*: skema Pydantic ketat; tiap fakta punya `fact_id`, sumber, dan `fetched_at`.
- [ ] **T-031 · Penulis artikel (outline → draft) + claim_map** (L) · dep: T-030, T-004
  *Terima*: gagal-parse diulang maksimal 2×; seluruh kalimat bernilai fakta punya `claim_id`.
- [ ] **T-032 · Adaptasi bilingual ID + EN** (M) · dep: T-031
  Satu slug, dua `article_i18n`.
  *Terima*: dua versi dengan klaim identik secara faktual.
- [ ] **T-033 · Prompt gambar + alt text** (S) · dep: T-031
  1 hero + 2 pendukung: prompt, negative prompt, rasio, alt ID/EN; tanpa merek/orang nyata. Tidak ada generasi/unggah gambar.
  *Terima*: lolos validasi skema dan daftar larangan kata.
- [ ] **T-034 · Snippet Threads (≥ 6 sudut, TEXT)** (M) · dep: T-031
  ≤ 500 karakter byte-aware, 1 topic tag, tautan `/id/{slug}` atau `/en/{slug}`, hashtag AI pendek.
  *Terima*: 100% snippet lolos validator panjang; tidak ada dua snippet dengan pembuka identik.
- [ ] **T-035 · Spec 007 QA dasar** (M) · dep: T-031, T-032, T-022
  Grounding berbasis kode (angka, nama, bintang terhadap Fact Pack), kemiripan judul `pg_trgm`, anti-salin verbatim (n-gram), label AI + `data_as_of`. LLM-hakim masuk roadmap.
  *Terima*: artikel dengan klaim palsu sengaja disisipkan **ditolak** dan snippet-nya tidak pernah `ready`; artikel bersih lulus.
- [ ] **T-044 · Endpoint admin minimal + auth Supabase JWT** (M) · dep: T-003 *(dimajukan: dibutuhkan T-036)*
  `pipeline/run`, `kill-switch`, `queue`.
  *Terima*: endpoint admin menolak token non-operator.
- [ ] **T-036 · Orkestrator pipeline end-to-end** (M) · dep: T-022, T-034, T-035, T-044
  *Terima*: `POST /v1/admin/pipeline/run` menghasilkan artikel `ready` (atau `rejected` dengan alasan) beserta log biaya.

## Fase 5 — Blog API & Threads Nyata

- [ ] **T-040 · Spec 008 API publik** (M) · dep: T-036
  Artikel (`lang=id|en`), hotel, feed JSON, RSS, sitemap; paginasi. Respons artikel dan hotel memuat `attribution` ("© OpenStreetMap contributors", "Overture Maps Foundation").
  *Terima*: OpenAPI valid; tes kontrak untuk tiap endpoint, termasuk keberadaan `attribution`.
- [ ] **T-041 · Penerbitan blog + webhook bertanda tangan** (S) · dep: T-040
  Set `published_at`, kirim webhook HMAC sekali (tanpa retry).
  *Terima*: penerima uji memvalidasi tanda tangan; gagal kirim tercatat di log, tidak membatalkan publish.
- [ ] **T-055 · Buffer `replenish`** (S) · dep: T-054, T-036, T-041
  Job tiap 6 jam: jika snippet `ready` dari artikel terbit < 24, picu pipeline. Slot tanpa konten → skip + alert.
  *Terima*: saat `ready` < 24 pipeline dipicu; saat kosong slot dilewati dengan alert.
- [ ] **T-056 · Uji coba akun uji** 🔴 (M) · dep: T-055, T-064
  Jalankan 48 jam di akun uji dengan konten nyata.
  *Terima*: ≥ 99% slot terkirim, deviasi ≤ 5 menit.
- [ ] **T-042 · Klien TypeScript dari OpenAPI** (S) · dep: T-040 *(bila waktu cukup)*
- [ ] **T-043 · Frontend demo (Next.js)** (M) · dep: T-041, T-042 *(bila waktu cukup)*
  Rute `/id/[slug]` dan `/en/[slug]`, revalidate lewat webhook, footer atribusi OSM + Overture.

---

## Roadmap (ditunda dari irisan assessment)

- T-013 provider web terkelola (Firecrawl/Playwright, allowlist + robots.txt)
- T-014 provider TripAdvisor Content API
- T-053 unggah gambar ke Supabase Storage + posting IMAGE; adapter `ImageProvider`
- T-061 laporan harian · T-062 dashboard operator · T-063 hardening keamanan lanjutan · T-065 metrik performa
- Retry webhook, LLM-hakim untuk grounding naratif, penyedia embedding, mode review manual + pool evergreen
- Kanal tambahan, harga real-time, wilayah di luar Bali

---

## Urutan Kritis

```
T-001 → S-1, T-002, T-005
T-001 → T-003, T-004 → T-037, T-060
T-003 → T-050 → T-051 → T-052
                  ↓
               T-054 (dummy) → T-064 deploy awal
T-003 → T-010 → T-011/T-012 → T-015 → T-017 → T-016
                                        ↓
                      T-020 → T-021 → T-022
                                ↓
                      T-030 → T-031 → T-032/033/034 → T-035 → T-036 (+T-044)
                                                                ↓
                                              T-040 → T-041 → T-055 → T-056
```

## Pemeriksaan Sebelum Demo

- [ ] Kill-switch diuji dan terdokumentasi
- [ ] Artikel gagal QA terbukti tidak diposting
- [ ] Semua provider memiliki catatan ToS dan TTL cache di `sources`
- [ ] Runbook token Threads tersedia
- [ ] Label AI dan `data_as_of` tampil di blog; hashtag AI di snippet
- [ ] Footer atribusi "© OpenStreetMap contributors" + Overture Maps tampil di blog
