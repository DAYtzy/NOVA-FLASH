// NOVA FLASH — frontend biasa (tanpa framework), satu halaman untuk auth + app.
const $ = (s) => document.querySelector(s);
const state = { token: localStorage.getItem("nf_token") || "", user: null, page: { name: "feed" } };

function toast(msg) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.remove("hidden");
  clearTimeout(toast._h);
  toast._h = setTimeout(() => t.classList.add("hidden"), 2200);
}

function initials(name) {
  return (name || "?").trim().slice(0, 1).toUpperCase();
}

function avatarEl(user, size) {
  const d = document.createElement("div");
  d.className = "avatar";
  if (size) { d.style.width = size + "px"; d.style.height = size + "px"; }
  if (user.avatar) {
    d.style.backgroundImage = `url(${user.avatar})`;
  } else {
    d.textContent = initials(user.full_name || user.username);
  }
  return d;
}

async function api(path, opts = {}) {
  const headers = Object.assign({}, opts.headers || {});
  if (opts.body && !(opts.body instanceof FormData)) headers["Content-Type"] = "application/json";
  if (state.token) headers["Authorization"] = "Bearer " + state.token;
  const res = await fetch("/api" + path, Object.assign({}, opts, { headers }));
  let data = {};
  try { data = await res.json(); } catch (_) { /* no body */ }
  if (!res.ok) throw new Error(data.error || ("Error " + res.status));
  return data;
}

// ---------- auth ----------

function showAuth() {
  $("#authScreen").classList.remove("hidden");
  $("#app").classList.add("hidden");
}

function showApp() {
  $("#authScreen").classList.add("hidden");
  $("#app").classList.remove("hidden");
}

$("#toRegister").onclick = () => { $("#loginForm").classList.add("hidden"); $("#registerForm").classList.remove("hidden"); };
$("#toLogin").onclick = () => { $("#registerForm").classList.add("hidden"); $("#loginForm").classList.remove("hidden"); };

$("#loginBtn").onclick = async () => {
  $("#loginErr").textContent = "";
  try {
    const d = await api("/login", { method: "POST", body: JSON.stringify({ who: $("#loginWho").value, email: $("#loginWho").value, username: $("#loginWho").value, password: $("#loginPw").value }) });
    onAuthed(d);
  } catch (e) { $("#loginErr").textContent = e.message; }
};

$("#regBtn").onclick = async () => {
  $("#regErr").textContent = "";
  try {
    const d = await api("/register", {
      method: "POST", body: JSON.stringify({
        full_name: $("#regName").value, username: $("#regUsername").value, email: $("#regEmail").value,
        birth_year: $("#regYear").value, password: $("#regPw").value, agree: $("#regAgree").checked,
      }),
    });
    onAuthed(d);
  } catch (e) { $("#regErr").textContent = e.message; }
};

function onAuthed(d) {
  state.token = d.token;
  state.user = d.user;
  localStorage.setItem("nf_token", d.token);
  showApp();
  go({ name: "feed" });
}

$("#logoutBtn").onclick = () => {
  state.token = "";
  localStorage.removeItem("nf_token");
  showAuth();
};

// ---------- navigasi sederhana ----------

function go(page) {
  state.page = page;
  if (page.name === "feed") renderFeed();
  else if (page.name === "profile") renderProfile(page.username);
}

$("#profileBtn").onclick = () => go({ name: "profile", username: state.user.username });

// ---------- feed ----------

function postCard(p) {
  const el = document.createElement("div");
  el.className = "post";
  el.dataset.id = p.id;

  const head = document.createElement("div");
  head.className = "post-head";
  head.appendChild(avatarEl(p.owner));
  const uname = document.createElement("a");
  uname.className = "uname";
  uname.textContent = p.owner.username;
  uname.onclick = () => go({ name: "profile", username: p.owner.username });
  head.appendChild(uname);
  el.appendChild(head);

  const media = document.createElement(p.kind === "video" ? "video" : "img");
  media.className = "post-media";
  media.src = p.media;
  if (p.kind === "video") { media.controls = true; media.playsInline = true; }
  el.appendChild(media);

  const actions = document.createElement("div");
  actions.className = "post-actions";
  const likeBtn = document.createElement("button");
  likeBtn.textContent = p.liked ? "♥" : "♡";
  if (p.liked) likeBtn.classList.add("liked");
  likeBtn.onclick = async () => {
    try {
      const d = await api(`/posts/${p.id}/like`, { method: p.liked ? "DELETE" : "POST" });
      p.liked = d.liked; p.likes = d.likes;
      likeBtn.textContent = p.liked ? "♥" : "♡";
      likeBtn.classList.toggle("liked", p.liked);
      likesEl.textContent = p.likes + " suka";
    } catch (e) { toast(e.message); }
  };
  actions.appendChild(likeBtn);
  const commentBtn = document.createElement("button");
  commentBtn.textContent = "💬";
  commentBtn.onclick = () => toggleComments(el, p);
  actions.appendChild(commentBtn);
  el.appendChild(actions);

  const likesEl = document.createElement("div");
  likesEl.className = "post-likes";
  likesEl.textContent = p.likes + " suka";
  el.appendChild(likesEl);

  if (p.caption) {
    const cap = document.createElement("div");
    cap.className = "post-caption";
    const b = document.createElement("b"); b.textContent = p.owner.username;
    cap.appendChild(b);
    cap.appendChild(document.createTextNode(p.caption));
    el.appendChild(cap);
  }

  const commentsLink = document.createElement("button");
  commentsLink.className = "post-comments-link";
  commentsLink.textContent = p.comments > 0 ? `Lihat ${p.comments} komentar` : "Jadi yang pertama berkomentar";
  commentsLink.onclick = () => toggleComments(el, p);
  el.appendChild(commentsLink);

  const time = document.createElement("div");
  time.className = "post-time";
  time.textContent = new Date(p.t).toLocaleString("id-ID");
  el.appendChild(time);

  const form = document.createElement("div");
  form.className = "comment-form";
  const input = document.createElement("input");
  input.placeholder = "Tambahkan komentar...";
  const send = document.createElement("button");
  send.textContent = "Kirim";
  send.onclick = async () => {
    const body = input.value.trim();
    if (!body) return;
    try {
      await api(`/posts/${p.id}/comments`, { method: "POST", body: JSON.stringify({ body }) });
      input.value = "";
      p.comments++;
      commentsLink.textContent = `Lihat ${p.comments} komentar`;
      if (el.querySelector(".comment-list")) loadComments(el, p);
    } catch (e) { toast(e.message); }
  };
  form.appendChild(input); form.appendChild(send);
  el.appendChild(form);

  return el;
}

async function toggleComments(el, p) {
  let list = el.querySelector(".comment-list");
  if (list) { list.remove(); return; }
  list = document.createElement("div");
  list.className = "comment-list";
  el.insertBefore(list, el.querySelector(".comment-form"));
  await loadComments(el, p);
}

async function loadComments(el, p) {
  const list = el.querySelector(".comment-list");
  if (!list) return;
  list.innerHTML = "";
  try {
    const d = await api(`/posts/${p.id}/comments`);
    d.comments.forEach((c) => {
      const row = document.createElement("div");
      row.className = "comment-row";
      const b = document.createElement("b"); b.textContent = c.author.username;
      row.appendChild(b);
      row.appendChild(document.createTextNode(c.body));
      list.appendChild(row);
    });
  } catch (e) { toast(e.message); }
}

async function renderFeed() {
  const view = $("#view");
  view.innerHTML = "";
  try {
    const d = await api("/feed");
    if (!d.posts.length) {
      view.innerHTML = '<div class="empty">Belum ada post. Jadilah yang pertama memposting! ➕</div>';
      return;
    }
    d.posts.forEach((p) => view.appendChild(postCard(p)));
  } catch (e) { toast(e.message); }
}

// ---------- profil ----------

async function renderProfile(username) {
  const view = $("#view");
  view.innerHTML = "";
  try {
    const d = await api(`/users/${username}/posts`);
    const head = document.createElement("div");
    head.className = "profile-head";
    head.appendChild(avatarEl(d.user, 80));
    const info = document.createElement("div");
    info.innerHTML = `
      <div class="profile-name">${d.user.full_name} <span style="color:var(--muted)">@${d.user.username}</span></div>
      <div class="profile-stats">
        <div><b>${d.posts.length}</b>Post</div>
        <div><b>${d.followers}</b>Pengikut</div>
        <div><b>${d.following}</b>Mengikuti</div>
      </div>
      <div class="profile-bio">${d.user.bio || ""}</div>`;
    head.appendChild(info);
    view.appendChild(head);

    if (d.user.username !== state.user.username) {
      const btn = document.createElement("button");
      btn.className = "follow-btn " + (d.you_follow ? "yes" : "no");
      btn.textContent = d.you_follow ? "Mengikuti" : "Ikuti";
      btn.style.margin = "0 16px 16px";
      btn.onclick = async () => {
        try {
          const r = await api(`/users/${username}/follow`, { method: d.you_follow ? "DELETE" : "POST" });
          d.you_follow = r.following;
          btn.className = "follow-btn " + (d.you_follow ? "yes" : "no");
          btn.textContent = d.you_follow ? "Mengikuti" : "Ikuti";
        } catch (e) { toast(e.message); }
      };
      view.appendChild(btn);
    } else {
      const btn = document.createElement("button");
      btn.className = "btn-ghost";
      btn.style.margin = "0 16px 16px";
      btn.textContent = "Edit bio";
      btn.onclick = async () => {
        const bio = prompt("Bio baru (maks 150 karakter):", d.user.bio || "");
        if (bio === null) return;
        try {
          const r = await api("/me/profile", { method: "POST", body: JSON.stringify({ bio }) });
          state.user = r.user;
          renderProfile(username);
        } catch (e) { toast(e.message); }
      };
      view.appendChild(btn);
    }

    const grid = document.createElement("div");
    grid.className = "grid";
    d.posts.forEach((p) => {
      const m = document.createElement(p.kind === "video" ? "video" : "img");
      m.src = p.media;
      m.onclick = () => go({ name: "feed" }); // versi awal: klik kembali ke feed (lightbox bisa ditambah nanti)
      grid.appendChild(m);
    });
    view.appendChild(grid);
  } catch (e) { toast(e.message); }
}

// ---------- posting baru ----------

let pendingMediaData = "";
let pendingMediaKind = "";

$("#newPostBtn").onclick = () => {
  $("#postErr").textContent = "";
  $("#mediaInput").value = "";
  $("#mediaPreviewImg").classList.add("hidden");
  $("#mediaPreviewVid").classList.add("hidden");
  $("#captionInput").value = "";
  $("#submitPostBtn").disabled = true;
  pendingMediaData = ""; pendingMediaKind = "";
  $("#newPostModal").classList.remove("hidden");
};
$("#cancelPostBtn").onclick = () => $("#newPostModal").classList.add("hidden");

$("#mediaInput").onchange = () => {
  const f = $("#mediaInput").files[0];
  if (!f) return;
  if (f.size > 6_000_000) {
    $("#postErr").textContent = "File maksimal ~6MB pada versi ini.";
    return;
  }
  const reader = new FileReader();
  reader.onload = () => {
    pendingMediaData = reader.result;
    pendingMediaKind = f.type.startsWith("video") ? "video" : "image";
    if (pendingMediaKind === "video") {
      $("#mediaPreviewVid").src = pendingMediaData;
      $("#mediaPreviewVid").classList.remove("hidden");
      $("#mediaPreviewImg").classList.add("hidden");
    } else {
      $("#mediaPreviewImg").src = pendingMediaData;
      $("#mediaPreviewImg").classList.remove("hidden");
      $("#mediaPreviewVid").classList.add("hidden");
    }
    $("#submitPostBtn").disabled = false;
  };
  reader.readAsDataURL(f);
};

$("#submitPostBtn").onclick = async () => {
  $("#postErr").textContent = "";
  $("#submitPostBtn").disabled = true;
  try {
    await api("/posts", { method: "POST", body: JSON.stringify({ media: pendingMediaData, caption: $("#captionInput").value }) });
    $("#newPostModal").classList.add("hidden");
    go({ name: "feed" });
  } catch (e) {
    $("#postErr").textContent = e.message;
    $("#submitPostBtn").disabled = false;
  }
};

// ---------- mulai ----------

(async function start() {
  if (!state.token) { showAuth(); return; }
  try {
    const d = await api("/me");
    state.user = d.user;
    showApp();
    go({ name: "feed" });
  } catch (_) {
    state.token = "";
    localStorage.removeItem("nf_token");
    showAuth();
  }
})();

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/sw.js").catch(() => {});
}
