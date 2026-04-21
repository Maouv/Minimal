import sys
import os
from pathlib import Path

# Setup path
sys.path.insert(0, os.path.abspath('min/backend'))

print("Mengecek import...")
try:
    from coder import apply_edits
    from commands import EditMode
    print("✅ Import berhasil!")
except Exception as e:
    print(f"❌ Error saat import: {e}")
    sys.exit(1)

# 1. BUAT FILE TEST FISIK
filename = "test.txt"
content_awal = "baris lama\nbaris tetap\nbaris yang dihapus\n"
Path(filename).write_text(content_awal)
print(f"📝 File {filename} dibuat.")

# 2. DATA UNTUK TEST (Pake format yang paling simpel biar regex gak pusing)
mock_response = """```diff
--- test.txt
+++ test.txt
@@ -1,3 +1,3 @@
-baris lama
+baris baru yang keren
 baris tetap
-baris yang dihapus
+baris pengganti
```"""

files = {filename: content_awal}

print("\n🚀 Menjalankan apply_edits...")
try:
    # Kita panggil fungsinya
    results = apply_edits(mock_response, files, mode="udiff")

    # --- INI BARIS DEBUG-NYA ---
    print(f"DEBUG: Jumlah hasil edit yang ditemukan: {len(results)}")

    if not results:
        print("⚠️ Hasil kosong! Masalah ada di regex atau cara parsing di coder.py.")
    
    for res in results:
        if res.success:
            print(f"✅ BERHASIL! File: {res.file}")
            print("\n--- HASIL PERUBAHAN ---")
            print(res.updated)
        else:
            print(f"❌ GAGAL! File: {res.file}")
            print(f"Error: {res.error}")

except Exception as e:
    print(f"💥 Crash pas jalanin apply_edits: {e}")
    import traceback
    traceback.print_exc()

