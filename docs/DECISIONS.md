# DECISIONS — HotelPilot

Keputusan minimal yang diambil saat implementasi karena konflik/kekurangan di dokumen. Format: konteks → keputusan → alasan.

| # | Konteks | Keputusan | Alasan |
|---|---------|-----------|--------|
| D-01 | Instruksi pemilik: penyedia LLM diganti dari Claude API ke **Shiteru AI**, model "Kimi K3 Pro". Katalog Shiteru (dicek 18 Nov 2026) tidak memuat ID "kimi-k3-pro"; yang ada `kimi-k3.1-pro` (Kimi K3.1 Pro), `kimi-k3`, `kimi-k3:premium`. | Default `LLM_MODEL=kimi-k3.1-pro`, bisa diganti lewat `.env`. Endpoint OpenAI-compatible `LLM_BASE_URL=https://shiteru.id/v1` (`/chat/completions`, `Authorization: Bearer`). Semua penyebutan "Claude API" di PRD/ARCH dibaca sebagai klien LLM tunggal `core/llm.py`. | Nama paling dekat dengan permintaan; tetap dapat dikonfigurasi. |
| D-02 | Shiteru melaporkan biaya sebagai `usage.billing.billed_tokens` (token saldo), bukan USD; anggaran di spec dalam USD. | `cost_usd = billed_tokens × LLM_USD_PER_M_BILLED_TOKENS / 1e6` (default 0,09 ≈ Rp1.500/1M token saldo). Bila `billing` tidak ada, pakai `total_tokens`. | Anggaran harian tetap dalam USD sesuai `settings.budget_daily_usd`. |
| D-03 | Shiteru dapat menambahkan "footer" teks di akhir jawaban. | Parser mengambil objek JSON pertama yang seimbang dari teks, lalu divalidasi Pydantic. | Footer tidak merusak parse. |
| D-04 | Kode retry Shiteru: 429/503 aman diulang; 402 = saldo habis; 401/403 = kredensial. | Retry exponential backoff + jitter hanya untuk timeout/transport/429/5xx; 4xx lain (termasuk 402) gagal langsung. | Sesuai dokumen "Errors and limits". |
