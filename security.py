"""Fungsi keamanan murni (tanpa database) supaya bisa diuji sendiri: header, pembatas laju, aturan password,
dan validasi gambar data-URL. Sama persis dengan punya NOVA WAWA (satu pola keamanan untuk semua app NOVA)."""
import os, re, time

# ---------- header keamanan ----------
CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
       "font-src 'self' https://fonts.gstatic.com data:; img-src 'self' data: blob: https://res.cloudinary.com; "
       "media-src 'self' blob: data: https://res.cloudinary.com; connect-src 'self' data: blob: https://api.cloudinary.com; "
       "object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'")
BASE_HEADERS = {
    "Content-Security-Policy": CSP,
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(self), microphone=(), geolocation=(), payment=()",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
}


def apply_headers(resp, path=""):
    for k, v in BASE_HEADERS.items():
        resp.headers.setdefault(k, v)
    if path.startswith("/api/") and "Cache-Control" not in resp.headers:
        resp.headers["Cache-Control"] = "no-store"
    return resp


# ---------- pembatas laju (di memori, per instance) ----------
class Limiter:
    def __init__(self):
        self.h = {}

    def hit(self, key, limit, secs):
        now = time.time()
        q = [t for t in self.h.get(key, []) if now - t < secs]
        ok = len(q) < limit
        if ok:
            q.append(now)
        self.h[key] = q
        if len(self.h) > 5000:
            self.h = {k: v for k, v in self.h.items() if v and now - v[-1] < 3600}
        return ok


# ---------- aturan password ----------
COMMON = {"12345678", "123456789", "1234567890", "password", "password1", "password123", "qwerty123", "qwertyuiop",
          "11111111", "00000000", "abc12345", "iloveyou", "admin123", "letmein1", "87654321", "asdfghjkl", "kontol123"}


def pw_problem(pw, name="", email=""):
    """Pesan masalah (Indonesia) kalau password terlalu lemah, atau None kalau boleh."""
    if len(pw) < 8:
        return "Password minimal 8 karakter."
    if len(pw.encode()) > 72:
        return "Password maksimal 72 karakter."
    low = pw.lower()
    if low in COMMON or len(set(low)) <= 2:
        return "Password terlalu mudah ditebak. Pakai kombinasi yang lebih unik."
    if any(len(x) >= 4 and x in low for x in re.split(r"\s+", name.strip().lower())):
        return "Password jangan memuat namamu."
    if email and low == email.strip().lower():
        return "Password jangan sama dengan email."
    return None


# ---------- validasi gambar/video data-URL (mencegah suntikan ke CSS/atribut) ----------
IMG_RE = re.compile(r"^data:image/(?:png|jpeg|webp);base64,[A-Za-z0-9+/]+={0,2}$")
VID_RE = re.compile(r"^data:video/(?:mp4|webm);base64,[A-Za-z0-9+/]+={0,2}$")


def safe_data_url(s, maxlen):
    return isinstance(s, str) and len(s) <= maxlen and bool(IMG_RE.match(s))


def safe_video_url(s, maxlen):
    return isinstance(s, str) and len(s) <= maxlen and bool(VID_RE.match(s))
