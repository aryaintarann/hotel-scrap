# DECISIONS — HotelPilot

Keputusan minimal yang diambil saat implementasi karena konflik/kekurangan di dokumen. Format: konteks → keputusan → alasan.

| # | Konteks | Keputusan | Alasan |
|---|---------|-----------|--------|
| D-01 | Instruksi pemilik: penyedia LLM diganti dari Claude API ke **Shiteru AI**, model "Kimi K3 Pro". Katalog Shiteru (dicek 18 Nov 2026) tidak memuat ID "kimi-k3-pro"; yang ada `kimi-k3.1-pro` (Kimi K3.1 Pro), `kimi-k3`, `kimi-k3:premium`. | Default `LLM_MODEL=kimi-k3.1-pro`, bisa diganti lewat `.env`. Endpoint OpenAI-compatible `LLM_BASE_URL=https://shiteru.id/v1` (`/chat/completions`, `Authorization: Bearer`). Semua penyebutan "Claude API" di PRD/ARCH dibaca sebagai klien LLM tunggal `core/llm.py`. | Nama paling dekat dengan permintaan; tetap dapat dikonfigurasi. |
| D-02 | Shiteru melaporkan biaya sebagai `usage.billing.billed_tokens` (token saldo), bukan USD; anggaran di spec dalam USD. | `cost_usd = billed_tokens × LLM_USD_PER_M_BILLED_TOKENS / 1e6` (default 0,09 ≈ Rp1.500/1M token saldo). Bila `billing` tidak ada, pakai `total_tokens`. | Anggaran harian tetap dalam USD sesuai `settings.budget_daily_usd`. |
| D-03 | Shiteru dapat menambahkan "footer" teks di akhir jawaban. | Parser mengambil objek JSON pertama yang seimbang dari teks, lalu divalidasi Pydantic. | Footer tidak merusak parse. |
| D-04 | Kode retry Shiteru: 429/503 aman diulang; 402 = saldo habis; 401/403 = kredensial. | Retry exponential backoff + jitter hanya untuk timeout/transport/429/5xx; 4xx lain (termasuk 402) gagal langsung. | Sesuai dokumen "Errors and limits". |
| D-05 | T-001/T-003/T-005 tercentang di TASKS.md tetapi repo kosong (hanya `docs/`). | Dikerjakan ulang dari nol; centang dipertahankan setelah tes lulus. | Instruksi "kerjakan dari nol". |
| D-06 | ARCH: DB = Supabase terkelola; target pemilik: `docker compose up` menjalankan seluruh sistem termasuk DB. | Compose menyertakan Postgres 17 (`pg_trgm`). Migrasi di `supabase/migrations/` kompatibel Supabase (peran `anon/authenticated/service_role` dibuat bila belum ada). Untuk Supabase terkelola cukup set `DATABASE_URL`. | Satu perintah, tanpa akun eksternal. |
| D-07 | ARCH §6 kurang kolom untuk beberapa kebutuhan (lihat `specs/001-schema.md` "Additions"). | Kolom tambahan minimal, tanpa mengubah kolom yang ada. | Dibutuhkan oleh deteksi perubahan, QA, log. |
| D-08 | FR-43 "dead-letter setelah 3 gagal" vs ARCH §8 "retry 1 → 5 → 15 mnt, lalu dead". | `max_attempts = 4`: 1 percobaan + 3 retry (1, 5, 15 mnt), lalu `dead` + alert. | Memenuhi urutan jeda ARCH; 3 retry gagal = dead. |
| D-09 | S-1/T-051/T-064/T-056 butuh akun & token Threads uji + VPS; belum tersedia. | Kontrak diuji dengan respons ter-mock; `DummyChannel` menjalankan alur penuh tanpa token; `scripts/spike_threads.py` siap dijalankan begitu `.env` diisi. Task yang kriterianya butuh akun nyata **tidak dicentang**. | Tidak berhenti, tidak mengklaim verifikasi yang tidak terjadi. |
| D-10 | Validasi 500 karakter "byte-aware". | Panjang = jumlah byte UTF-8 ≤ 500 (selalu ≥ jumlah karakter, jadi margin otomatis). | Aman untuk emoji. |
