# 🚀 InnovaTex Amlogic S905X4 Kernel Builder (CI/CD)

Automated Kernel Compilation and Packaging Engine for **Amlogic S905X4 (Advan AT01 / ah212 generic)** running bare-metal Arch Linux ARM.

Developed by **Fariz (@InnovaTex)** & Antigravity AI Pair Programmer.

---

## ⚡ Fitur Utama
1. **GitHub Actions Cloud Runner**: Cross-compile AArch64 hanya dalam hitungan menit tanpa membebani hardware lokal.
2. **Integrated Wireless Drivers**:
   - **Unisoc UWE5631**: Wi-Fi (`sprdwl_ng.ko`) & Bluetooth HCI (`sprdbt_tty.ko` + `uwe5621_bsp_sdio.ko`).
   - **Ralink RT5370**: Native Linux driver (`rt2800usb`) dengan dukungan penuh Monitor Mode & Packet Injection.
3. **Firmware Bundling**:
   - Firmware binary [`wcnmodem.bin`](firmware/wcnmodem.bin) & [`rt2870.bin`](firmware/rt2870.bin) otomatis dimasukkan ke direktori `/lib/firmware/`.
4. **Boot Partition Image Packaging**:
   - Otomatis merakit file image partisi boot FAT32 **`kernel_boot_*.fat`** (256MB) yang siap di-flash menggunakan [`flash.py`](https://github.com/InnovaTexProject).
5. **Unified Release**:
   - Menghasilkan file ZIP lengkap berisi `kernel_boot.fat`, arsip modul & firmware `modules_and_firmware_*.tar.gz`, dan verifikasi checksum SHA-256.

---

## 🛠️ Cara Trigger Build dari Terminal TV Box

### 1. Trigger via GitHub CLI (`gh`):
```bash
# Jalankan mode cepat (Fast Devmfc LTS 6.18.55) - ~2 Menit selesai:
gh workflow run build.yml -f build_mode=fast_devmfc_package

# Jalankan mode full compile source kernel dari Devmfc Meson64:
gh workflow run build.yml -f build_mode=full_source_compile -f kernel_branch=meson64-6.14
```

### 2. Pantau Progress Realtime:
```bash
gh run watch
```

### 3. Download Hasil Rilis ke Folder Downloads:
```bash
gh run download
```

---

## 💾 Struktur Folder Proyek
- `.github/workflows/build.yml` : Mesin CI/CD GitHub Actions.
- `boot_scripts/`               : U-Boot autoscripts & dynamic box config (Devmfc S905X4 generic).
- `configs/`                    : Konfigurasi kernel `.config` Meson64.
- `drivers/unisoc/`             : Source code driver combo Unisoc UWE5631 (BSP, WIFI, BT).
- `firmware/`                   : Firmware biner (`wcnmodem.bin`, `rt2870.bin`, dll.).
