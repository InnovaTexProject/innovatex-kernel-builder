#!/usr/bin/env python3
"""
InnovaTex Flash Engine v4.2 - Amlogic S905X4 Workstation Edition
Designed for Fariz (@InnovaTex)
Antislop UI/UX Architecture + Universal Android Termux & Bare-Metal Linux Support
"""

import os
import subprocess
import sys
import shutil
import tempfile
import time
import shlex

# ---------- DETEKSI ENVIRONMENT & PATHS ----------
IS_ANDROID = os.path.exists("/system") or "ANDROID_ROOT" in os.environ

if IS_ANDROID and os.path.exists("/sdcard"):
    SAFE_ROOT = "/sdcard"
    DEFAULT_BROWSE_DIR = "/sdcard/Download" if os.path.exists("/sdcard/Download") else "/sdcard"
else:
    SAFE_ROOT = os.path.expanduser("~")
    DEFAULT_BROWSE_DIR = os.path.join(SAFE_ROOT, "Downloads") if os.path.exists(os.path.join(SAFE_ROOT, "Downloads")) else SAFE_ROOT

LOG_FILE = os.path.join(SAFE_ROOT, "flash_debug.log")
SAFE_PREFIXES = ("sd", "mmcblk1", "mmcblk2")

IMAGE_EXT = (".img", ".iso", ".raw")
COMPRESSED_EXT = (".gz", ".xz", ".zst", ".bz2", ".lz4", ".lzma")
ROOTFS_EXT = (".tar", ".tar.gz", ".tar.xz", ".tar.zst", ".tar.bz2")
FIRMWARE_EXT = IMAGE_EXT + COMPRESSED_EXT + (".fat",)

REQUIRED_PKGS = {
    "coreutils": "dd",
    "util-linux": "wipefs",
    "gzip": "zcat",
    "xz-utils": "xz",
    "zstd": "zstd",
    "bzip2": "bzcat",
    "e2fsprogs": "mkfs.ext4",
    "dosfstools": "mkfs.vfat",
    "parted": "parted",
    "tar": "tar",
    "p7zip": "7z",
}

# ---------- STATE GLOBAL ----------
DEBUG_MODE = False

# ---------- WARNA & TIPOGRAFI (ANTISLOP PALETTE) ----------
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
WHITE = "\033[97m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def clear_screen():
    if not DEBUG_MODE:
        os.system("clear" if os.name == "posix" else "cls")


def print_banner(subtitle=""):
    clear_screen()
    print(f"{CYAN}┌─────────────────────────────────────────────────────────────┐{RESET}")
    print(f"{CYAN}│{RESET}  {BOLD}{WHITE}INNOVATEX FLASH ENGINE v4.2{RESET} {DIM}── Amlogic S905X4 Workstation{RESET}   {CYAN}│{RESET}")
    print(f"{CYAN}│{RESET}  {DIM}Universal Host:{RESET} {GREEN}{'Android Termux' if IS_ANDROID else 'Arch Linux ARM (Native)'}{RESET}                       {CYAN}│{RESET}")
    if subtitle:
        pad = 59 - len(subtitle)
        print(f"{CYAN}├─────────────────────────────────────────────────────────────┤{RESET}")
        print(f"{CYAN}│{RESET}  {YELLOW}{subtitle}{' ' * max(0, pad - 2)}{CYAN}│{RESET}")
    print(f"{CYAN}└─────────────────────────────────────────────────────────────┘{RESET}\n")


def log_step(status, msg):
    badges = {
        "INFO": f"{BLUE}[INFO]{RESET}",
        "WAIT": f"{CYAN}[⏳]{RESET}",
        "DONE": f"{GREEN}[DONE]{RESET}",
        "WARN": f"{YELLOW}[WARN]{RESET}",
        "FAIL": f"{RED}[FAIL]{RESET}",
        "STEP": f"{MAGENTA}[STEP]{RESET}",
    }
    badge = badges.get(status, f"[{status}]")
    print(f" {badge} {msg}")


def run_silent(cmd, shell=False):
    global DEBUG_MODE
    cmd_str = cmd if isinstance(cmd, str) else " ".join(cmd)
    
    if DEBUG_MODE:
        print(f" {DIM}[EXEC]{RESET} {cmd_str}")
        return subprocess.run(cmd, shell=shell)
    else:
        with open(LOG_FILE, "a") as f:
            f.write(f"\n--- [{time.strftime('%Y-%m-%d %H:%M:%S')}] EXEC: {cmd_str} ---\n")
            res = subprocess.run(cmd, shell=shell, stdout=f, stderr=subprocess.STDOUT)
            f.write(f"Return code: {res.returncode}\n")
            if res.returncode != 0:
                log_step("WARN", f"Perintah latar belakang return error code {res.returncode}. Cek {LOG_FILE}")
            return res


def do_sync():
    log_step("WAIT", "Menyinkronkan cache memori ke fisik storage (sync)...")
    run_silent(["sync"])
    log_step("DONE", "Sinkronisasi fisik storage selesai.")


def resolve_dev_path(name):
    clean_name = os.path.basename(name)
    if os.path.exists(f"/dev/block/{clean_name}"):
        return f"/dev/block/{clean_name}"
    return f"/dev/{clean_name}"


def get_part_prefix(block_dev):
    clean = os.path.basename(block_dev)
    is_sd = clean.startswith("sd")
    has_dev_block = os.path.exists(f"/dev/block/{clean}")
    
    base_dir = "/dev/block" if has_dev_block else "/dev"
    if is_sd:
        return f"{base_dir}/{clean}"
    return f"{base_dir}/{clean}p"


def check_sudo():
    log_step("INFO", "Memverifikasi hak akses root...")
    if not shutil.which("sudo"):
        if IS_ANDROID:
            log_step("WARN", "Package 'tsu' tidak ditemukan. Mencoba instalasi via pkg...")
            run_silent("pkg update -y && pkg install -y tsu", shell=True)
        if not shutil.which("sudo"):
            log_step("FAIL", "Akses 'sudo' tidak ditemukan di sistem. Harap jalankan di environment root.")
            sys.exit(1)
            
    if run_silent(["sudo", "whoami"]).returncode == 0:
        log_step("DONE", "Akses Root (UID 0) terverifikasi aktif.")
    else:
        log_step("FAIL", "Otorisasi Root ditolak!")
        sys.exit(1)


def check_and_install_packages():
    missing = []
    for pkg, binary in REQUIRED_PKGS.items():
        alt_bin = "7za" if pkg == "p7zip" else None
        if not (shutil.which(binary) or (alt_bin and shutil.which(alt_bin))):
            missing.append(pkg)

    if missing:
        log_step("WARN", f"Menginstal dependensi yang belum tersedia: {', '.join(missing)}")
        if IS_ANDROID and shutil.which("pkg"):
            run_silent(["pkg", "update", "-y"])
            run_silent(["pkg", "install", "-y"] + missing)
        elif shutil.which("pacman"):
            run_silent(["sudo", "pacman", "-S", "--noconfirm", "--needed"] + missing)
    log_step("DONE", "Seluruh perkakas biner siap digunakan.")


def list_block_devices():
    devices = []
    result = subprocess.run(["sudo", "lsblk", "-dn", "-o", "NAME,SIZE,TYPE,MODEL"], capture_output=True, text=True)
    if result.returncode != 0:
        return devices
    for line in result.stdout.splitlines():
        parts = line.strip().split(None, 3)
        if len(parts) < 3:
            continue
        name, size, dtype = parts[0], parts[1], parts[2]
        model = parts[3] if len(parts) > 3 else ""
        if dtype != "disk" or not any(name.startswith(p) for p in SAFE_PREFIXES) or name.startswith("mmcblk0"):
            continue
        real_path = resolve_dev_path(name)
        devices.append((real_path, size, model))
    return devices


def choose_block_device():
    print_banner("Deteksi Penyimpanan Eksternal")
    devices = list_block_devices()
    if not devices:
        log_step("FAIL", "Tidak ada SD Card atau USB Flashdisk eksternal yang terdeteksi!")
        print(f"\n {YELLOW}Pastikan MicroSD sudah terpasang di card reader OTG / slot SD.{RESET}\n")
        sys.exit(1)

    print(f" {BOLD}Pilih Media Target Flashing:{RESET}\n")
    for i, (dev, size, model) in enumerate(devices, 1):
        print(f"   [{GREEN}{i}{RESET}] {BOLD}{dev}{RESET}  {CYAN}[{size}]{RESET}  {DIM}({model}){RESET}")
    print(f"   [{RED}0{RESET}] Keluar dari Program\n")

    while True:
        choice = input(f" {BOLD}{GREEN}Masukkan nomor target ❯ {RESET}").strip()
        if choice == "0":
            clear_screen()
            print(f"{GREEN}Operasi dibatalkan. Sampai jumpa bro!{RESET}\n")
            sys.exit(0)
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(devices):
                return devices[idx][0]
        except ValueError:
            pass


def get_mounted_partitions(block_dev):
    clean = os.path.basename(block_dev)
    mounted = []
    try:
        with open("/proc/mounts") as f:
            for line in f:
                parts = line.split()
                if len(parts) < 2:
                    continue
                node = parts[0]
                if clean in node:
                    mounted.append(parts[1])
    except Exception:
        pass
    return mounted


def unmount_device(block_dev):
    mounted = get_mounted_partitions(block_dev)
    if mounted:
        log_step("WAIT", f"Melepas partisi yang sedang aktif ({len(mounted)} partisi)...")
        for mnt in mounted:
            run_silent(["sudo", "umount", "-f", mnt])
        log_step("DONE", "Seluruh partisi pada target berhasil dilepas.")


def fix_ext4_partition(target_path):
    q_target = shlex.quote(target_path)
    run_silent(f"sudo e2fsck -pf {q_target}", shell=True)
    run_silent(f"sudo tune2fs -O ^metadata_csum,^64bit {q_target}", shell=True)
    run_silent(f"sudo resize2fs -s {q_target}", shell=True)
    run_silent(f"sudo e2fsck -yf {q_target}", shell=True)


def format_and_partition(block_dev, boot_mb=512, boot_label="ALARMBOOT", root_label="ROOTFS"):
    print_banner(f"Partisi Ulang & Format Target: {block_dev}")
    unmount_device(block_dev)
    
    log_step("STEP", "Membersihkan metadata partisi lama (wipefs)...")
    run_silent(["sudo", "wipefs", "-a", block_dev])
    run_silent(["sudo", "dd", "if=/dev/zero", f"of={block_dev}", "bs=1M", "count=32", "status=none"])
    
    log_step("STEP", f"Menyusun tabel partisi MBR (msdos) dengan Bootable Flag...")
    run_silent(["sudo", "parted", "-s", block_dev, "mklabel", "msdos"])
    run_silent(["sudo", "parted", "-s", block_dev, "mkpart", "primary", "fat32", "1MiB", f"{boot_mb}MiB"])
    
    # [KRUSIAL UNTUK AMLOGIC U-BOOT] Set bootable flag & LBA flag
    run_silent(["sudo", "parted", "-s", block_dev, "set", "1", "boot", "on"])
    run_silent(["sudo", "parted", "-s", block_dev, "set", "1", "lba", "on"])
    
    run_silent(["sudo", "parted", "-s", block_dev, "mkpart", "primary", "ext4", f"{boot_mb}MiB", "100%"])
    run_silent(["sudo", "partprobe", block_dev])
    time.sleep(2)

    part_prefix = get_part_prefix(block_dev)
    boot_part = f"{part_prefix}1"
    root_part = f"{part_prefix}2"
    
    log_step("STEP", f"Membuat sistem berkas FAT32 ({boot_label}) pada {boot_part}...")
    run_silent(["sudo", "mkfs.vfat", "-F", "32", "-n", boot_label, boot_part])
    
    log_step("STEP", f"Membuat sistem berkas EXT4 ({root_label}) pada {root_part}...")
    run_silent(["sudo", "mkfs.ext4", "-F", "-L", root_label, root_part])
    
    do_sync()
    log_step("DONE", "Struktur partisi MBR bootable berhasil dibuat dan siap diinjeksi.")
    return boot_part, root_part


def browse_file(start_dir=None, title="Pilih File", allowed_ext=None, allow_dir_selection=False, multi_select=False):
    if not start_dir or not os.path.exists(start_dir):
        start_dir = DEFAULT_BROWSE_DIR
    current = os.path.abspath(start_dir)
    
    while True:
        print_banner(title)
        print(f" {BOLD}Direktori Aktif:{RESET} {CYAN}{current}{RESET}\n")
        try:
            entries = sorted(os.listdir(current))
        except Exception:
            current = DEFAULT_BROWSE_DIR
            continue
            
        dirs, files = [], []
        for e in entries:
            full = os.path.join(current, e)
            if os.path.isdir(full):
                dirs.append(e)
            elif os.path.isfile(full):
                files.append(e)

        print(f"   [{YELLOW}0{RESET}] ⬆️  Naik satu level direktori")
        if allow_dir_selection:
            print(f"   [{CYAN}s{RESET}] 📌 Pilih folder saat ini: ({os.path.basename(current) or '/'})")
            
        display_idx = 1
        for d in dirs:
            print(f"   [{YELLOW}{display_idx}{RESET}] 📁 {d}/")
            display_idx += 1
            
        valid_files = []
        for f in files:
            match = allowed_ext is None or f.lower().endswith(allowed_ext)
            if not match:
                continue
            valid_files.append(f)
            
            size_bytes = os.path.getsize(os.path.join(current, f))
            size_mb = size_bytes / (1024 * 1024)
            size_str = f"{size_mb:.1f} MB" if size_mb >= 1 else f"{size_bytes / 1024:.0f} KB"
            
            icon = "📄"
            if f.lower().endswith(IMAGE_EXT): icon = "💿"
            elif f.lower().endswith(ROOTFS_EXT): icon = "📦"
            elif f.lower().endswith(".fat"): icon = "💾"
            elif f.lower().endswith(COMPRESSED_EXT): icon = "🗜️"
            
            print(f"   [{GREEN}{display_idx}{RESET}] {icon} {BOLD}{f}{RESET}  {DIM}({size_str}){RESET}")
            display_idx += 1

        print(f"   [{RED}x{RESET}] Batal & Kembali\n")

        prompt = f" {BOLD}{GREEN}Pilih nomor (bisa multi, pisahkan spasi: 1 3) ❯ {RESET}" if multi_select else f" {BOLD}{GREEN}Pilih nomor ❯ {RESET}"
        choice = input(prompt).strip().lower()
        
        if choice == "x":
            return [] if multi_select else None
        if allow_dir_selection and choice == "s":
            return [current] if multi_select else current
        if choice == "0":
            current = os.path.dirname(current) if current != "/" else current
            continue

        parts = choice.replace(",", " ").split()
        if not parts:
            continue

        if multi_select and len(parts) > 1:
            selected = []
            for p in parts:
                try:
                    idx = int(p) - 1
                    if 0 <= idx < len(dirs):
                        selected.append(os.path.join(current, dirs[idx]))
                    else:
                        file_idx = idx - len(dirs)
                        if 0 <= file_idx < len(valid_files):
                            selected.append(os.path.join(current, valid_files[file_idx]))
                except ValueError:
                    pass
            if selected:
                return selected
            continue
            
        try:
            idx = int(parts[0]) - 1
            if 0 <= idx < len(dirs):
                current = os.path.join(current, dirs[idx])
            else:
                file_idx = idx - len(dirs)
                if 0 <= file_idx < len(valid_files):
                    sel = os.path.join(current, valid_files[file_idx])
                    return [sel] if multi_select else sel
        except ValueError:
            pass


def extract_rootfs(rootfs_path, mount_dir):
    log_step("STEP", f"Mengekstrak Rootfs OS: {os.path.basename(rootfs_path)}...")
    q_rootfs = shlex.quote(rootfs_path)
    q_mount = shlex.quote(mount_dir)
    
    if rootfs_path.lower().endswith(".tar.xz"):
        cmd = f"sudo xz -dc {q_rootfs} | sudo tar -xpf - -C {q_mount} --numeric-owner"
    elif rootfs_path.lower().endswith(".tar.gz"):
        cmd = f"sudo zcat {q_rootfs} | sudo tar -xpf - -C {q_mount} --numeric-owner"
    elif rootfs_path.lower().endswith(".tar.zst"):
        cmd = f"sudo zstd -dc {q_rootfs} | sudo tar -xpf - -C {q_mount} --numeric-owner"
    else:
        cmd = f"sudo tar -xpf {q_rootfs} -C {q_mount} --numeric-owner"
        
    res = run_silent(cmd, shell=True)
    if res.returncode != 0:
        log_step("FAIL", "Ekstraksi rootfs mengalami galat!")
        return False

    # Flatten nested rootfs jika arsip dibungkus dalam single parent directory
    r = subprocess.run(["sudo", "ls", "-1A", mount_dir], capture_output=True, text=True)
    entries = [e for e in r.stdout.splitlines() if e != "lost+found"]
    if len(entries) == 1:
        s_folder = os.path.join(mount_dir, entries[0])
        if subprocess.run(["sudo", "test", "-d", s_folder]).returncode == 0:
            log_step("INFO", f"Meratakan struktur direktori nested ({entries[0]})...")
            run_silent(["sudo", "bash", "-c", f"shopt -s dotglob nullglob; mv {shlex.quote(s_folder)}/* {q_mount}/"])
            run_silent(["sudo", "rmdir", s_folder])

    # Injeksi DNS darurat
    run_silent(["sudo", "bash", "-c", f"echo 'nameserver 1.1.1.1' > {q_mount}/etc/resolv.conf"])
    run_silent(["sudo", "bash", "-c", f"echo 'nameserver 8.8.8.8' >> {q_mount}/etc/resolv.conf"])
    do_sync()
    log_step("DONE", "Rootfs OS terpasang rapi.")
    return True


def extract_modules_and_firmware(tarball_path, root_mount_dir):
    log_step("STEP", f"Mengekstrak Modul & Firmware: {os.path.basename(tarball_path)}...")
    q_src = shlex.quote(tarball_path)
    q_mnt = shlex.quote(root_mount_dir)
    
    if tarball_path.lower().endswith(".tar.xz"):
        cmd = f"sudo xz -dc {q_src} | sudo tar -xpf - -C {q_mnt} --numeric-owner"
    elif tarball_path.lower().endswith(".tar.gz"):
        cmd = f"sudo zcat {q_src} | sudo tar -xpf - -C {q_mnt} --numeric-owner"
    else:
        cmd = f"sudo tar -xpf {q_src} -C {q_mnt} --numeric-owner"
        
    res = run_silent(cmd, shell=True)
    if res.returncode == 0:
        log_step("DONE", "Modul & Firmware berhasil diinjeksi ke Rootfs.")
    else:
        log_step("FAIL", "Gagal mengekstrak arsip modul & firmware.")
        return False
        
    # Verifikasi keberadaan file kritis
    fw_wcn = os.path.join(root_mount_dir, "lib", "firmware", "wcnmodem.bin")
    fw_rt = os.path.join(root_mount_dir, "lib", "firmware", "rt2870.bin")
    
    has_wcn = subprocess.run(["sudo", "test", "-f", fw_wcn]).returncode == 0
    has_rt = subprocess.run(["sudo", "test", "-f", fw_rt]).returncode == 0
    
    log_step("INFO", f"Verifikasi Firmware: wcnmodem.bin = {'TERPASANG' if has_wcn else 'TIDAK ADA'} | rt2870.bin = {'TERPASANG' if has_rt else 'TIDAK ADA'}")
    do_sync()
    return True


def flash_boot_partition_from_fat(fat_src, boot_part, work_dir):
    log_step("STEP", f"Menginjeksi Partisi Boot dari: {os.path.basename(fat_src)}...")
    tgt_b_mnt = os.path.join(work_dir, "tboot")
    os.makedirs(tgt_b_mnt, exist_ok=True)
    
    # Mount partisi boot target
    run_silent(["sudo", "mount", boot_part, tgt_b_mnt])
    run_silent(["sudo", "find", tgt_b_mnt, "-mindepth", "1", "-delete"])
    
    # Ekstrak seluruh isi .fat ke partisi boot menggunakan 7z
    q_fat = shlex.quote(fat_src)
    q_tgt = shlex.quote(tgt_b_mnt)
    log_step("WAIT", "Menyalin file bootloader (Image, DTB, autoscripts, boot.config)...")
    res = run_silent(f"sudo 7z x -y {q_fat} -o{q_tgt}", shell=True)
    
    if res.returncode == 0:
        log_step("DONE", "Seluruh berkas bootloader berhasil disalin utuh.")
    else:
        log_step("FAIL", "Galat saat mengekstrak biner partisi boot!")
        
    do_sync()
    run_silent(["sudo", "umount", tgt_b_mnt])
    return res.returncode == 0


def action_innovatex_3in1(block_dev):
    print_banner("MODE RESMI: INNOVATEX 3-IN-1 CUSTOM FLASHER")
    print(f" {BOLD}Mode ini khusus untuk setup Native Kernel (seperti Linux 7.3) + OS + Firmware.{RESET}\n")
    
    # 1. Pilih Kernel Boot FAT
    print(f" {BOLD}LANGKAH 1 DARI 3:{RESET} Pilih file biner partisi boot ({CYAN}.fat{RESET})")
    fat_src = browse_file(DEFAULT_BROWSE_DIR, "1. Pilih File Partisi Boot (.fat)", allowed_ext=(".fat",))
    if not fat_src:
        return

    # 2. Pilih Rootfs Tarball
    print(f"\n {BOLD}LANGKAH 2 DARI 3:{RESET} Pilih arsip Rootfs OS ({CYAN}.tar.xz / .tar.gz{RESET})")
    rootfs_src = browse_file(DEFAULT_BROWSE_DIR, "2. Pilih File Rootfs OS", allowed_ext=ROOTFS_EXT)
    if not rootfs_src:
        return

    # 3. Pilih Modules & Firmware
    print(f"\n {BOLD}LANGKAH 3 DARI 3:{RESET} Pilih arsip Modul & Firmware ({CYAN}modules_and_firmware_*.tar.gz{RESET})")
    mod_src = browse_file(DEFAULT_BROWSE_DIR, "3. Pilih Arsip Modul & Firmware", allowed_ext=ROOTFS_EXT)
    if not mod_src:
        return

    # Konfirmasi Akhir (Antislop Confirmation Screen)
    print_banner("RINGKASAN EKSEKUSI FLASHING 3-IN-1")
    print(f" {BOLD}Target Media Storage :{RESET} {RED}{block_dev}{RESET}")
    print(f" {BOLD}1. Boot Partition    :{RESET} {CYAN}{os.path.basename(fat_src)}{RESET}")
    print(f" {BOLD}2. Rootfs OS Tarball :{RESET} {CYAN}{os.path.basename(rootfs_src)}{RESET}")
    print(f" {BOLD}3. Modul & Firmware  :{RESET} {CYAN}{os.path.basename(mod_src)}{RESET}")
    print(f"\n {BOLD}{RED}PERINGATAN: Seluruh isi {block_dev} akan diformat ulang secara permanen!{RESET}")
    
    confirm = input(f"\n {BOLD}{YELLOW}Ketik 'GAS' untuk memulai proses flashing ❯ {RESET}").strip()
    if confirm != "GAS":
        print(f"\n {YELLOW}Flashing dibatalkan. Media target tidak disentuh.{RESET}\n")
        time.sleep(2)
        return

    w_dir = tempfile.mkdtemp()
    t_start = time.time()
    try:
        # A. Format & Partisi MBR dengan Boot Flag
        p_boot, p_root = format_and_partition(block_dev, boot_mb=512, boot_label="ALARMBOOT", root_label="ROOTFS")

        # B. Injeksi Partisi Boot
        flash_boot_partition_from_fat(fat_src, p_boot, w_dir)

        # C. Injeksi Partisi Rootfs
        tgt_r_mnt = os.path.join(w_dir, "troot")
        os.makedirs(tgt_r_mnt, exist_ok=True)
        
        fix_ext4_partition(p_root)
        run_silent(["sudo", "mount", p_root, tgt_r_mnt])
        
        extract_rootfs(rootfs_src, tgt_r_mnt)
        extract_modules_and_firmware(mod_src, tgt_r_mnt)
        
        do_sync()
        run_silent(["sudo", "umount", tgt_r_mnt])

        t_elapsed = time.time() - t_start
        print_banner("FLASHING 3-IN-1 SELESAI DENGAN SUKSES! 🚀")
        print(f" {GREEN}[OK] Media MicroSD siap digunakan pada Amlogic S905X4!{RESET}")
        print(f" {DIM}Waktu Total Eksekusi:{RESET} {CYAN}{t_elapsed:.1f} detik{RESET}\n")
        print(f" {BOLD}Langkah Selanjutnya:{RESET}")
        print(f"  1. Cabut MicroSD dengan aman dari card reader.")
        print(f"  2. Tancapkan ke slot MicroSD TV Box S905X4.")
        print(f"  3. Nyalakan TV Box. U-Boot akan otomatis mendeteksi partisi bootable dan menjalankan kernel.")
        print(f"  4. Nikmati Linux 7.3 Mainline di Arch Linux ARM lu!")
        
    finally:
        run_silent(["sudo", "rm", "-rf", w_dir])
        input(f"\n {CYAN}Tekan Enter untuk kembali ke Menu Utama...{RESET}")


def action_flash_img(block_dev):
    img = browse_file(DEFAULT_BROWSE_DIR, "Mode Flash Raw Image", IMAGE_EXT + COMPRESSED_EXT)
    if not img:
        return
    print(f"\n {BOLD}{RED}PERINGATAN: SELURUH DATA DI {block_dev} AKAN DIHAPUS TOTAL!{RESET}")
    if input(f" {YELLOW}Ketik 'YA' untuk konfirmasi ❯ {RESET}").strip() != "YA":
        return
    
    unmount_device(block_dev)
    log_step("STEP", f"Mem-flash image {os.path.basename(img)} ke {block_dev}...")
    
    lower = img.lower()
    q_img = shlex.quote(img)
    if lower.endswith(".gz"):
        cmd = f"zcat {q_img} | sudo dd of={block_dev} bs=4M status=progress conv=fsync"
    elif lower.endswith(".xz"):
        cmd = f"xz -dc {q_img} | sudo dd of={block_dev} bs=4M status=progress conv=fsync"
    else:
        cmd = f"sudo dd if={q_img} of={block_dev} bs=4M status=progress conv=fsync"
    
    subprocess.run(cmd, shell=True)
    do_sync()
    log_step("DONE", "Flashing Image selesai.")
    input(f"\n {CYAN}Tekan Enter untuk melanjutkan...{RESET}")


def action_backup(block_dev):
    print_banner("Mode Backup & Cloning Image")
    print(f"   [{YELLOW}1{RESET}] Backup Partisi Boot Saja (.fat)")
    print(f"   [{YELLOW}2{RESET}] Backup Partisi Rootfs Saja (.tar.xz)")
    print(f"   [{YELLOW}3{RESET}] Full Clone Seluruh SD Card ke Raw Image (.img.xz) -> {GREEN}Siap Flash 1-Click{RESET}")
    print(f"   [{RED}0{RESET}] Kembali\n")
    
    c = input(f" {BOLD}{GREEN}Pilih opsi ❯ {RESET}").strip()
    if c == "0":
        return
    
    dest = DEFAULT_BROWSE_DIR
    os.makedirs(dest, exist_ok=True)
    p_boot = f"{get_part_prefix(block_dev)}1"
    p_root = f"{get_part_prefix(block_dev)}2"
    ts = time.strftime("%Y%m%d_%H%M")
    unmount_device(block_dev)
    
    if c == "1":
        f_out = os.path.join(dest, f"kernel_boot_backup_{ts}.fat")
        log_step("STEP", f"Mem-backup partisi boot ke {f_out}...")
        run_silent(["sudo", "dd", f"if={p_boot}", f"of={f_out}", "bs=4M", "status=progress"])
        log_step("DONE", f"Backup partisi boot berhasil tersimpan.")
    elif c == "2":
        f_out = os.path.join(dest, f"rootfs_backup_{ts}.tar.xz")
        log_step("STEP", f"Mem-backup rootfs ke {f_out}...")
        fix_ext4_partition(p_root)
        w_dir = tempfile.mkdtemp()
        run_silent(["sudo", "mount", p_root, w_dir])
        q_wdir, q_out = shlex.quote(w_dir), shlex.quote(f_out)
        cmd = f"sudo tar --numeric-owner -cpf - -C {q_wdir} . | xz -T4 -v > {q_out}"
        subprocess.run(cmd, shell=True)
        run_silent(["sudo", "umount", w_dir])
        shutil.rmtree(w_dir, ignore_errors=True)
        log_step("DONE", "Backup rootfs selesai.")
    elif c == "3":
        f_out = os.path.join(dest, f"innovatex_s905x4_full_clone_{ts}.img.xz")
        q_out = shlex.quote(f_out)
        print(f"\n {BOLD}{YELLOW}Mem-packing seluruh isi SD Card menjadi image terkompresi...{RESET}")
        cmd = f"sudo dd if={block_dev} bs=4M status=progress | xz -T4 -v > {q_out}"
        subprocess.run(cmd, shell=True)
        log_step("DONE", f"Image Utuh Siap Flash (.img.xz) selesai dibuat di: {f_out}")
        
    input(f"\n {CYAN}Tekan Enter untuk melanjutkan...{RESET}")


def action_chroot_interactive(block_dev):
    p_root = f"{get_part_prefix(block_dev)}2"
    print_banner(f"Chroot Terminal OS Target: {p_root}")
    unmount_device(block_dev)
    fix_ext4_partition(p_root)
    
    w_dir = tempfile.mkdtemp()
    mnt = os.path.join(w_dir, "chroot_tgt")
    os.makedirs(mnt, exist_ok=True)
    
    try:
        run_silent(["sudo", "mount", p_root, mnt])
        for fs in ["proc", "sys"]:
            run_silent(["sudo", "mount", "-t", fs, fs, f"{mnt}/{fs}"])
        run_silent(["sudo", "mount", "-o", "bind", "/dev", f"{mnt}/dev"])
        run_silent(["sudo", "mount", "-o", "bind", "/dev/pts", f"{mnt}/dev/pts"])
        run_silent(["sudo", "mount", "-t", "tmpfs", "tmpfs", f"{mnt}/run"])
        
        shell = "/bin/bash" if os.path.exists(os.path.join(mnt, "bin", "bash")) else "/bin/sh"
        log_step("DONE", f"Environment Chroot siap. Membuka subshell {shell}...")
        print(f" {DIM}(Ketik 'exit' untuk keluar dari chroot){RESET}\n")
        subprocess.run(["sudo", "chroot", mnt, shell])
    finally:
        do_sync()
        for v in ["run", "dev/pts", "dev", "sys", "proc", ""]:
            run_silent(["sudo", "umount", "-f", os.path.join(mnt, v)])
        run_silent(["sudo", "rm", "-rf", w_dir])
        input(f"\n {CYAN}Tekan Enter untuk kembali...{RESET}")


def main():
    global DEBUG_MODE
    clear_screen()
    check_sudo()
    check_and_install_packages()
    
    if not os.path.exists(LOG_FILE):
        open(LOG_FILE, "a").close()
        
    block_dev = choose_block_device()

    while True:
        print_banner("Menu Utama Flasher")
        print(f" {BOLD}Penyimpanan Terpilih:{RESET} {YELLOW}{block_dev}{RESET}\n")
        print(f"   [{GREEN}1{RESET}] {BOLD}🚀 Flash InnovaTex 3-in-1{RESET} {CYAN}(Kernel Boot .fat + Rootfs + Modules/Firmware){RESET}")
        print(f"   [{GREEN}2{RESET}] 💿 Flash Raw Image {YELLOW}(.img / .img.gz / .img.xz){RESET}")
        print(f"   [{GREEN}3{RESET}] 💾 Backup & Cloning {YELLOW}(Dump .fat, Rootfs .tar, atau Full Image .img.xz){RESET}")
        print(f"   [{GREEN}4{RESET}] 💻 Masuk Terminal OS {YELLOW}(Chroot Interaktif){RESET}")
        print(f"   [{GREEN}5{RESET}] 🐞 Toggle Debug Verbose {YELLOW}(Status: {'ON' if DEBUG_MODE else 'OFF'}){RESET}")
        print(f"   [{RED}0{RESET}] Keluar dari Program\n")
        
        mode = input(f" {BOLD}{GREEN}Pilih Menu ❯ {RESET}").strip()
        
        if mode == "0":
            clear_screen()
            print(f"{GREEN}Operasi selesai. Selamat menikmati setup Amlogic S905X4 bro!{RESET}\n")
            break
        elif mode == "1":
            action_innovatex_3in1(block_dev)
        elif mode == "2":
            action_flash_img(block_dev)
        elif mode == "3":
            action_backup(block_dev)
        elif mode == "4":
            action_chroot_interactive(block_dev)
        elif mode == "5":
            DEBUG_MODE = not DEBUG_MODE
            print(f"\n {GREEN}[OK] Debug Mode diubah menjadi: {'ON' if DEBUG_MODE else 'OFF'}{RESET}")
            time.sleep(1)


if __name__ == "__main__":
    main()
