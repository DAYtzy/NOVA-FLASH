import os, re, time, secrets, bcrypt
from datetime import datetime, timedelta
from functools import wraps
from dotenv import load_dotenv
load_dotenv()
from flask import Flask, request, jsonify, send_from_directory
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from database import Session, User, Post, Like, Comment, Follow, RateHit, init_db
from security import apply_headers, pw_problem, safe_data_url, safe_video_url

BASE = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__)

SECRET = os.getenv("SECRET_KEY", "").strip()
SECRET_OK = len(SECRET) >= 16
ON_VERCEL = bool(os.getenv("VERCEL"))
ser = URLSafeTimedSerializer(SECRET if SECRET_OK else "dev-secret-change-me")  # kunci cadangan HANYA untuk komputer lokal
init_db()

MIN_AGE = 13  # umur minimal pendaftar; harus sama dengan Syarat Penggunaan dan batas di formulir
USERNAME_RE = re.compile(r"^[a-z0-9_](?:[a-z0-9_.]{1,28}[a-z0-9_])?$")
MEDIA_MAX = 6_000_000  # ~6MB per data-URL (batas aman untuk disimpan di database kalau belum pasang Cloudinary)
PUBLIC_FILES = {"index.html", "style.css", "script.js", "sw.js", "manifest.json", "icon-192.png", "icon-512.png"}


@app.before_request
def guard_secret():
    if ON_VERCEL and not SECRET_OK and request.path.startswith("/api/"):
        return jsonify(error="Server belum aman: SECRET_KEY belum diisi di Vercel (minimal 16 karakter).", config=True), 503


@app.after_request
def sec_headers(r):
    return apply_headers(r, request.path)


def new_pid(db):
    while True:  # ID angka acak 8 digit (tanpa awalan 0), diulang sampai belum dipakai — sama pola dengan NOVA WAWA
        pid = str(secrets.randbelow(90_000_000) + 10_000_000)
        if not db.query(User.id).filter_by(player_id=pid).first():
            return pid


def client_ip():
    return (request.headers.get("x-real-ip") or (request.headers.get("x-forwarded-for") or "").split(",")[0].strip() or request.remote_addr or "?")[:45]


def too_many(db, key, limit, secs):
    since = datetime.utcnow() - timedelta(seconds=secs)
    return (db.query(func.count(RateHit.id)).filter(RateHit.key == key, RateHit.ts > since).scalar() or 0) >= limit


def note_hit(db, key):
    db.add(RateHit(key=key[:120], ts=datetime.utcnow()))
    db.commit()
    if secrets.randbelow(40) == 0:  # sesekali buang catatan lama
        db.query(RateHit).filter(RateHit.ts < datetime.utcnow() - timedelta(days=1)).delete(synchronize_session=False)
        db.commit()


def make_token(u):
    import hashlib
    v = hashlib.sha256(u.password_hash.encode()).hexdigest()[:10]
    return ser.dumps([u.id, v])


def load_user(db):
    import hashlib
    try:
        v = ser.loads(request.headers.get("Authorization", "")[7:], max_age=30 * 86400)
        if not (isinstance(v, list) and len(v) == 2):
            return None
        u = db.get(User, v[0])
        if not u or hashlib.sha256(u.password_hash.encode()).hexdigest()[:10] != v[1]:
            return None
        return u
    except (BadSignature, SignatureExpired, TypeError, ValueError):
        return None


def authed(f):
    @wraps(f)
    def w(*a, **k):
        with Session() as db:
            u = load_user(db)
            if not u:
                return jsonify(error="Unauthorized"), 401
            return f(db, u, *a, **k)
    return w


def post_public(db, p, me_pid, author_cache):
    a = author_cache.get(p.owner)
    if a is None:
        a = db.query(User).filter_by(player_id=p.owner).first()
        author_cache[p.owner] = a
    likes = db.query(func.count()).select_from(Like).filter(Like.post_id == p.id).scalar() or 0
    liked = db.query(Like.post_id).filter_by(post_id=p.id, player_id=me_pid).first() is not None
    comments = db.query(func.count()).select_from(Comment).filter(Comment.post_id == p.id).scalar() or 0
    return {"id": p.id, "owner": a.public() if a else {"player_id": p.owner, "username": "?", "full_name": "?", "avatar": ""},
            "kind": p.kind, "media": p.media, "caption": p.caption or "",
            "likes": likes, "liked": liked, "comments": comments,
            "t": p.created_at.isoformat() + "Z"}


# ---------- auth ----------

@app.post("/api/register")
def register():
    d = request.get_json(silent=True) or {}
    name = (d.get("full_name") or "").strip()
    username = (d.get("username") or "").strip().lower()
    email = (d.get("email") or "").strip().lower()
    pw = d.get("password") or ""
    try:
        year = int(d.get("birth_year"))
    except (TypeError, ValueError, OverflowError):
        year = 0
    cy = time.gmtime().tm_year
    if not name or "@" not in email or len(email) > 120 or len(name) > 60 or not cy - 120 <= year <= cy:
        return jsonify(error="Data tidak valid."), 400
    if cy - year < MIN_AGE:
        return jsonify(error="Kamu harus berusia minimal %d tahun untuk memakai NOVA FLASH." % MIN_AGE), 400
    if not USERNAME_RE.match(username):
        return jsonify(error="Username 3-30 huruf kecil/angka/titik/garis bawah, tidak boleh diawali/diakhiri simbol."), 400
    if not d.get("agree"):
        return jsonify(error="Setujui Syarat dan Kebijakan Privasi dulu."), 400
    bad = pw_problem(pw, name, email)
    if bad:
        return jsonify(error=bad), 400
    hashed = bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()
    ip = client_ip()
    with Session() as db:
        if too_many(db, "R:" + ip, 6, 3600):
            return jsonify(error="Terlalu banyak pendaftaran dari jaringan ini. Coba lagi nanti."), 429
        note_hit(db, "R:" + ip)
        if db.query(User.id).filter_by(email=email).first():
            return jsonify(error="Email sudah terdaftar."), 409
        if db.query(User.id).filter_by(username=username).first():
            return jsonify(error="Username sudah dipakai."), 409
        for _ in range(5):
            u = User(player_id=new_pid(db), username=username, full_name=name, birth_year=year, email=email, password_hash=hashed)
            db.add(u)
            try:
                db.commit()
                return jsonify(token=make_token(u), user=u.public(mine=True)), 201
            except IntegrityError:
                db.rollback()
        return jsonify(error="Gagal membuat akun, coba lagi."), 500


@app.post("/api/login")
def login():
    d = request.get_json(silent=True) or {}
    who = (d.get("email") or d.get("username") or "").strip().lower()[:120]
    pw = d.get("password") or ""
    ip = client_ip()
    with Session() as db:
        if too_many(db, "L:ip:" + ip, 40, 900) or too_many(db, "L:who:" + who, 8, 900):
            return jsonify(error="Terlalu banyak percobaan masuk. Tunggu sekitar 15 menit lalu coba lagi."), 429
        u = db.query(User).filter((User.email == who) | (User.username == who)).first()
        ok = False
        if u:
            try:
                ok = bcrypt.checkpw(pw.encode()[:72], u.password_hash.encode())
            except ValueError:
                ok = False
        if not ok:
            note_hit(db, "L:ip:" + ip)
            note_hit(db, "L:who:" + who)
            return jsonify(error="Email/username atau password salah."), 401
        return jsonify(token=make_token(u), user=u.public(mine=True))


@app.get("/api/me")
@authed
def me(db, u):
    return jsonify(user=u.public(mine=True))


# ---------- feed & post ----------

@app.get("/api/feed")
@authed
def feed(db, u):
    before = request.args.get("before", type=int)
    q = db.query(Post).order_by(Post.id.desc())
    if before:
        q = q.filter(Post.id < before)
    rows = q.limit(12).all()
    cache = {}
    return jsonify(posts=[post_public(db, p, u.player_id, cache) for p in rows])


@app.get("/api/users/<username>/posts")
@authed
def user_posts(db, u, username):
    target = db.query(User).filter_by(username=username.lower()).first()
    if not target:
        return jsonify(error="Pengguna tidak ditemukan."), 404
    rows = db.query(Post).filter_by(owner=target.player_id).order_by(Post.id.desc()).limit(60).all()
    cache = {target.player_id: target}
    return jsonify(user=target.public(), posts=[post_public(db, p, u.player_id, cache) for p in rows],
                    followers=db.query(func.count()).select_from(Follow).filter_by(target=target.player_id).scalar() or 0,
                    following=db.query(func.count()).select_from(Follow).filter_by(follower=target.player_id).scalar() or 0,
                    you_follow=db.query(Follow.target).filter_by(follower=u.player_id, target=target.player_id).first() is not None)


@app.post("/api/posts")
@authed
def create_post(db, u):
    d = request.get_json(silent=True) or {}
    media = d.get("media") or ""
    caption = (d.get("caption") or "").strip()[:2200]
    if safe_data_url(media, MEDIA_MAX):
        kind = "image"
    elif safe_video_url(media, MEDIA_MAX):
        kind = "video"
    else:
        return jsonify(error="Foto/video tidak valid atau terlalu besar (maks ~6MB untuk versi ini)."), 400
    if too_many(db, "P:" + u.player_id, 10, 3600):
        return jsonify(error="Terlalu sering memposting. Coba lagi nanti."), 429
    note_hit(db, "P:" + u.player_id)
    p = Post(owner=u.player_id, kind=kind, media=media, caption=caption)
    db.add(p)
    db.commit()
    return jsonify(post=post_public(db, p, u.player_id, {})), 201


@app.delete("/api/posts/<int:pid>")
@authed
def delete_post(db, u, pid):
    p = db.get(Post, pid)
    if not p or p.owner != u.player_id:
        return jsonify(error="Tidak ditemukan."), 404
    db.query(Like).filter_by(post_id=pid).delete()
    db.query(Comment).filter_by(post_id=pid).delete()
    db.delete(p)
    db.commit()
    return jsonify(ok=True)


# ---------- like & komentar ----------

@app.post("/api/posts/<int:pid>/like")
@authed
def like_post(db, u, pid):
    if not db.get(Post, pid):
        return jsonify(error="Tidak ditemukan."), 404
    if not db.query(Like.post_id).filter_by(post_id=pid, player_id=u.player_id).first():
        db.add(Like(post_id=pid, player_id=u.player_id))
        db.commit()
    n = db.query(func.count()).select_from(Like).filter_by(post_id=pid).scalar() or 0
    return jsonify(liked=True, likes=n)


@app.delete("/api/posts/<int:pid>/like")
@authed
def unlike_post(db, u, pid):
    db.query(Like).filter_by(post_id=pid, player_id=u.player_id).delete()
    db.commit()
    n = db.query(func.count()).select_from(Like).filter_by(post_id=pid).scalar() or 0
    return jsonify(liked=False, likes=n)


@app.get("/api/posts/<int:pid>/comments")
@authed
def list_comments(db, u, pid):
    rows = db.query(Comment).filter_by(post_id=pid).order_by(Comment.id.asc()).limit(200).all()
    authors = {a.player_id: a for a in db.query(User).filter(User.player_id.in_({c.player_id for c in rows} or {"-"}))}
    return jsonify(comments=[{"id": c.id, "body": c.body, "t": c.created_at.isoformat() + "Z",
                               "author": (authors.get(c.player_id).public() if authors.get(c.player_id) else
                                          {"player_id": c.player_id, "username": "?", "full_name": "?", "avatar": ""})}
                              for c in rows])


@app.post("/api/posts/<int:pid>/comments")
@authed
def add_comment(db, u, pid):
    if not db.get(Post, pid):
        return jsonify(error="Tidak ditemukan."), 404
    body = ((request.get_json(silent=True) or {}).get("body") or "").strip()[:500]
    if not body:
        return jsonify(error="Komentar kosong."), 400
    if too_many(db, "C:" + u.player_id, 30, 600):
        return jsonify(error="Terlalu sering berkomentar. Coba lagi nanti."), 429
    note_hit(db, "C:" + u.player_id)
    c = Comment(post_id=pid, player_id=u.player_id, body=body)
    db.add(c)
    db.commit()
    return jsonify(comment={"id": c.id, "body": c.body, "t": c.created_at.isoformat() + "Z", "author": u.public()}), 201


# ---------- follow ----------

@app.post("/api/users/<username>/follow")
@authed
def follow(db, u, username):
    target = db.query(User).filter_by(username=username.lower()).first()
    if not target or target.player_id == u.player_id:
        return jsonify(error="Tidak bisa mengikuti akun ini."), 400
    if not db.query(Follow.target).filter_by(follower=u.player_id, target=target.player_id).first():
        db.add(Follow(follower=u.player_id, target=target.player_id))
        db.commit()
    return jsonify(following=True)


@app.delete("/api/users/<username>/follow")
@authed
def unfollow(db, u, username):
    target = db.query(User).filter_by(username=username.lower()).first()
    if target:
        db.query(Follow).filter_by(follower=u.player_id, target=target.player_id).delete()
        db.commit()
    return jsonify(following=False)


@app.post("/api/me/profile")
@authed
def update_profile(db, u):
    d = request.get_json(silent=True) or {}
    if "bio" in d:
        u.bio = (d.get("bio") or "").strip()[:150]
    if "avatar" in d and (not d["avatar"] or safe_data_url(d["avatar"], 1_500_000)):
        u.avatar = d["avatar"] or ""
    db.commit()
    return jsonify(user=u.public(mine=True))


@app.get("/api/health")
def health():
    return jsonify(ok=True)


@app.get("/")
def home():
    return send_from_directory(BASE, "index.html")


@app.get("/<path:f>")
def static_files(f):
    if f in PUBLIC_FILES:
        r = send_from_directory(BASE, f)
        if f == "sw.js":
            r.headers["Cache-Control"] = "no-cache"
            r.headers["Service-Worker-Allowed"] = "/"
        elif f == "manifest.json":
            r.mimetype = "application/manifest+json"
        return r
    return "Not found", 404


if __name__ == "__main__":
    app.run(debug=True, port=5001, threaded=True)
